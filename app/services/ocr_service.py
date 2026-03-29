import os
import sys
import inspect
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
        self._gpu_ocr = None
        self._cpu_ocr = None

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

    @staticmethod
    def _format_result(result) -> str:
        extracted_text = []

        if result and result[0]:
            boxes = list(result[0])
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

    def _get_engine(self, use_gpu: bool):
        from paddleocr import PaddleOCR

        init_sig = inspect.signature(PaddleOCR.__init__)
        supports_use_gpu = "use_gpu" in init_sig.parameters

        if supports_use_gpu:
            common_kwargs = {
                "lang": "en",
                "show_log": False,
                "use_angle_cls": True,
                "use_gpu": use_gpu,
            }
        else:
            # PaddleOCR 3.x switched from `use_gpu` to `device`.
            common_kwargs = {
                "lang": "en",
                "use_angle_cls": True,
                "device": "gpu:0" if use_gpu else "cpu",
            }

        if use_gpu:
            if self._gpu_ocr is None:
                self._gpu_ocr = PaddleOCR(**common_kwargs)
            return self._gpu_ocr

        if self._cpu_ocr is None:
            self._cpu_ocr = PaddleOCR(**common_kwargs)
        return self._cpu_ocr

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

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return ""

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.3, beta=10)

        result = None

        try:
            result = self._get_engine(use_gpu=True).ocr(gray, cls=True)
        except Exception as gpu_error:
            if "No module named 'paddle'" in str(gpu_error):
                print(
                    "OCR dependency missing: install `paddlepaddle`/`paddlepaddle-gpu` "
                    "in a supported Python version."
                )
                return ""
            print(f"OCR GPU failed, retrying with CPU: {gpu_error}")
            try:
                result = self._get_engine(use_gpu=False).ocr(gray, cls=True)
            except Exception as cpu_error:
                if "No module named 'paddle'" in str(cpu_error):
                    print(
                        "OCR dependency missing: install `paddlepaddle`/`paddlepaddle-gpu` "
                        "in a supported Python version."
                    )
                    return ""
                print(f"OCR CPU failed: {cpu_error}")
                return ""

        return self._format_result(result)


ocr_service = OCRService()
