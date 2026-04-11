import gc
import os
import sys
import inspect
import tempfile
import threading
from pathlib import Path


class OCRService:
    """
    Simple PaddleOCR wrapper:
    - Applies Windows DLL bridge for GPU runtime
    - Preprocesses image (grayscale + mild contrast)
    - Tries GPU first, then CPU fallback
    """

    def __init__(self):
        self._bridge_ready = False
        self._runtime_ready = False
        self._gpu_ocr = None
        self._cpu_ocr = None
        self._ocr_lock = threading.Lock()
        self._cpu_threads = max(2, min(6, (os.cpu_count() or 8) // 2))
        self._opencv_threads = max(1, min(4, self._cpu_threads))
        self._gpu_memory_limit_mb = 3072
        self._rec_batch_num = 2
        self._cls_batch_num = 2

    def _setup_windows_bridge(self):
        if self._bridge_ready:
            return

        project_root = Path(__file__).resolve().parents[2]
        root_str = str(project_root)

        # Skip hoster connectivity checks during model init to avoid startup delay/noise.
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

        os.environ["PATH"] = root_str + os.pathsep + os.environ.get("PATH", "")

        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(root_str)
            except Exception as e:
                print(f"OCR DLL bridge warning (root): {e}")

            site_packages = Path(sys.prefix) / "Lib" / "site-packages"
            nvidia_base = site_packages / "nvidia"
            if nvidia_base.exists():
                for pkg in nvidia_base.iterdir():
                    bin_dir = pkg / "bin"
                    if bin_dir.exists():
                        try:
                            os.add_dll_directory(str(bin_dir))
                        except Exception:
                            continue
                        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")

        self._bridge_ready = True

    def _configure_runtime(self):
        if self._runtime_ready:
            return

        try:
            import cv2

            cv2.setNumThreads(self._opencv_threads)
        except Exception:
            pass

        try:
            import paddle

            if paddle.is_compiled_with_cuda():
                try:
                    total_gpu_mem_mb = int(
                        paddle.device.cuda.get_device_properties(0).total_memory / (1024 * 1024)
                    )
                    reserved_gpu_mem_mb = min(2048, max(1024, total_gpu_mem_mb // 3))
                    self._gpu_memory_limit_mb = max(
                        1024,
                        min(self._gpu_memory_limit_mb, total_gpu_mem_mb - reserved_gpu_mem_mb),
                    )
                except Exception:
                    pass

                paddle.set_flags(
                    {
                        "FLAGS_gpu_memory_limit_mb": self._gpu_memory_limit_mb,
                    }
                )
        except Exception as runtime_error:
            print(f"OCR runtime tuning warning: {runtime_error}")

        self._runtime_ready = True

    @staticmethod
    def _format_page_result(page_result) -> str:
        extracted_text = []

        if not page_result:
            return ""

        boxes = list(page_result)
        boxes.sort(key=lambda b: b[0][0][1] if b and b[0] else 0)

        for box in boxes:
            text = ""
            if len(box) > 1 and box[1]:
                text = box[1][0] or ""

            if not text:
                continue

            text = text.replace("+8", "B+").replace("8+", "B+")
            if text == "c+":
                text = "C+"

            extracted_text.append(text)

        return "  ".join(extracted_text).strip()

    @classmethod
    def _format_result(cls, result) -> str:
        if not result:
            return ""

        page_texts = []
        total_pages = len(result) if isinstance(result, list) else 0

        for page_index, page_result in enumerate(result, start=1):
            page_text = cls._format_page_result(page_result)
            if not page_text:
                continue

            if total_pages > 1:
                page_texts.append(f"Page {page_index}:\n{page_text}")
            else:
                page_texts.append(page_text)

        return "\n\n".join(page_texts).strip()

    def _get_engine(self, use_gpu: bool):
        self._setup_windows_bridge()
        self._configure_runtime()

        from paddleocr import PaddleOCR

        init_sig = inspect.signature(PaddleOCR.__init__)
        supports_use_gpu = "use_gpu" in init_sig.parameters

        common_kwargs = {
            "lang": "en",
            "show_log": False,
            "use_angle_cls": True,
            "cpu_threads": self._cpu_threads,
            "rec_batch_num": self._rec_batch_num,
            "cls_batch_num": self._cls_batch_num,
        }

        if supports_use_gpu:
            common_kwargs["use_gpu"] = use_gpu
        else:
            # PaddleOCR 3.x switched from `use_gpu` to `device`.
            common_kwargs["device"] = "gpu:0" if use_gpu else "cpu"

        if not use_gpu:
            common_kwargs["enable_mkldnn"] = False

        if use_gpu:
            if self._gpu_ocr is None:
                self._gpu_ocr = PaddleOCR(**common_kwargs)
            return self._gpu_ocr

        if self._cpu_ocr is None:
            self._cpu_ocr = PaddleOCR(**common_kwargs)
        return self._cpu_ocr

    @staticmethod
    def _shrink_engine_memory(engine, use_gpu: bool):
        if engine is None:
            return

        for attr_name in ("text_detector", "text_recognizer", "text_classifier"):
            predictor = getattr(getattr(engine, attr_name, None), "predictor", None)
            if predictor is None:
                continue

            try:
                predictor.try_shrink_memory()
            except Exception:
                pass

        if use_gpu:
            try:
                import paddle

                paddle.device.cuda.empty_cache()
            except Exception:
                pass

        gc.collect()

    def _run_ocr(self, input_value):
        with self._ocr_lock:
            gpu_engine = None
            try:
                gpu_engine = self._get_engine(use_gpu=True)
                return gpu_engine.ocr(input_value, cls=True)
            except Exception as gpu_error:
                if "No module named 'paddle'" in str(gpu_error):
                    print(
                        "OCR dependency missing: install `paddlepaddle`/`paddlepaddle-gpu` "
                        "in a supported Python version."
                    )
                    return None

                print(f"OCR GPU failed, retrying with CPU: {gpu_error}")
            finally:
                self._shrink_engine_memory(gpu_engine, use_gpu=True)

            cpu_engine = None
            try:
                cpu_engine = self._get_engine(use_gpu=False)
                return cpu_engine.ocr(input_value, cls=True)
            except Exception as cpu_error:
                if "No module named 'paddle'" in str(cpu_error):
                    print(
                        "OCR dependency missing: install `paddlepaddle`/`paddlepaddle-gpu` "
                        "in a supported Python version."
                    )
                    return None

                print(f"OCR CPU failed: {cpu_error}")
                return None
            finally:
                self._shrink_engine_memory(cpu_engine, use_gpu=False)

    def extract_text_from_image_bytes(self, image_bytes: bytes) -> str:
        if not image_bytes:
            return ""

        self._setup_windows_bridge()

        try:
            import cv2
            import numpy as np
        except Exception as import_error:
            print(f"OCR dependency import failed: {import_error}")
            return ""

        cv2.setNumThreads(self._opencv_threads)

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return ""

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.3, beta=10)

        result = self._run_ocr(gray)
        if not result:
            return ""

        return self._format_result(result)

    def extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        if not pdf_bytes:
            return ""

        self._setup_windows_bridge()

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = temp_file.name

            result = self._run_ocr(temp_path)
            if not result:
                return ""
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass

        return self._format_result(result)


ocr_service = OCRService()
