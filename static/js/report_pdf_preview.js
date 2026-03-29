function sanitizeFilenamePart(value, fallback) {
    const cleaned = String(value || "")
        .replace(/[\\/:*?"<>|]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    return (cleaned || fallback).slice(0, 80);
}

function getFilename() {
    const body = document.body;
    const userName = sanitizeFilenamePart(body.dataset.userName, "user");
    const topCareer = sanitizeFilenamePart(body.dataset.topCareer, "career");
    return `${userName}_${topCareer} - careersathi.pdf`;
}

function fitContentToSinglePage(page, content) {
    if (!page || !content) return 1;
    content.style.transform = "none";
    content.style.transformOrigin = "top left";
    content.style.width = "100%";

    const availableHeight = page.clientHeight || page.getBoundingClientRect().height;
    const requiredHeight = content.scrollHeight;

    if (!availableHeight || !requiredHeight || requiredHeight <= availableHeight) return 1;

    const scale = availableHeight / requiredHeight;
    content.style.transform = `scale(${scale})`;
    content.style.width = `${100 / scale}%`;
    return scale;
}

function fitPdfContentToSinglePage() {
    const page = document.getElementById("pdfPage");
    const content = document.getElementById("pdfContent");
    fitContentToSinglePage(page, content);
}

function extractCssUrls(backgroundImageValue) {
    const urls = [];
    const regex = /url\((['"]?)(.*?)\1\)/gi;
    let match;
    while ((match = regex.exec(backgroundImageValue || "")) !== null) {
        if (match[2]) urls.push(match[2].trim());
    }
    return urls;
}

function isSupportedDataImage(src) {
    return /^data:image\/(png|jpe?g|gif|bmp|svg\+xml|webp)(;|,)/i.test(src || "");
}

function isClearlyUnsupportedImageUrl(src) {
    if (!src) return true;
    const clean = src.trim().toLowerCase();

    if (clean.startsWith("data:image/")) {
        return !isSupportedDataImage(clean);
    }

    // Extension check for known problematic/rare formats in html2canvas pipelines.
    if (/\.(avif|heic|heif|jxl|tif|tiff)(\?|#|$)/i.test(clean)) {
        return true;
    }

    return false;
}

function stripRiskyBackgroundImages(root, aggressive = false) {
    if (!root) return;
    const elements = root.querySelectorAll("*");
    elements.forEach((el) => {
        const bg = window.getComputedStyle(el).backgroundImage || "";
        if (!bg || bg === "none") return;

        if (aggressive) {
            if (bg.includes("url(") || (!bg.includes("linear-gradient") && !bg.includes("radial-gradient"))) {
                el.style.backgroundImage = "none";
            }
            return;
        }

        const urls = extractCssUrls(bg);
        if (urls.length > 0 && urls.some(isClearlyUnsupportedImageUrl)) {
            el.style.backgroundImage = "none";
        }
    });
}

async function sanitizeImageElements(root, aggressive = false) {
    if (!root) return;
    const images = root.querySelectorAll("img");

    for (const img of images) {
        const src = img.getAttribute("src") || "";
        if (!src) {
            img.remove();
            continue;
        }

        if (aggressive || isClearlyUnsupportedImageUrl(src)) {
            img.remove();
        }
    }

    if (aggressive) {
        root.querySelectorAll("picture,source").forEach((el) => el.remove());
    }
}

function removeCssContentImages(root) {
    if (!root) return;
    const sanitizerStyle = document.createElement("style");
    sanitizerStyle.textContent = `
        *::before,
        *::after {
            content: none !important;
            background-image: none !important;
        }
    `;
    root.prepend(sanitizerStyle);
}

async function waitForRenderStability() {
    if (document.fonts && document.fonts.ready) {
        try {
            await document.fonts.ready;
        } catch (err) {
            console.warn("Font readiness check failed:", err);
        }
    }
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

function createExportClone() {
    const sourcePage = document.getElementById("pdfPage");
    if (!sourcePage) return null;

    const wrapper = document.createElement("div");
    wrapper.className = "pdf-export-wrapper";
    wrapper.style.position = "fixed";
    wrapper.style.left = "-10000px";
    wrapper.style.top = "0";
    wrapper.style.width = "210mm";
    wrapper.style.height = "297mm";
    wrapper.style.overflow = "hidden";
    wrapper.style.opacity = "0";
    wrapper.style.pointerEvents = "none";
    wrapper.style.background = "#fff";
    wrapper.style.zIndex = "-1";

    const clonePage = sourcePage.cloneNode(true);
    clonePage.removeAttribute("id");
    clonePage.style.width = "210mm";
    clonePage.style.height = "297mm";
    clonePage.style.margin = "0";
    clonePage.style.border = "none";
    clonePage.style.borderRadius = "0";
    clonePage.style.boxShadow = "none";

    const cloneContent = clonePage.querySelector("#pdfContent") || clonePage.querySelector(".pdf-content");
    if (cloneContent && cloneContent.id) {
        cloneContent.removeAttribute("id");
    }

    wrapper.appendChild(clonePage);
    document.body.appendChild(wrapper);

    if (cloneContent) {
        fitContentToSinglePage(clonePage, cloneContent);
    }

    return { wrapper, clonePage };
}

function getPdfOptions() {
    return {
        margin: 0,
        filename: getFilename(),
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: {
            scale: 1.5,
            useCORS: true,
            allowTaint: false,
            backgroundColor: "#ffffff",
            removeContainer: true,
            logging: false
        },
        jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
        pagebreak: { mode: ["css"] }
    };
}

function isUnsupportedImageTypeError(err) {
    const message = String((err && err.message) || err || "");
    return /unsupported image type/i.test(message);
}

async function downloadPdf() {
    const btn = document.getElementById("downloadPdfBtn");
    const page = document.getElementById("pdfPage");
    if (!btn || !page) return;

    if (!window.html2pdf) {
        alert("PDF tool failed to load. Please refresh and try again.");
        return;
    }

    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-gear"></i> Preparing...';

    fitPdfContentToSinglePage();
    let exportWrapper = null;

    try {
        await waitForRenderStability();

        const exportNode = createExportClone();
        if (!exportNode || !exportNode.clonePage) {
            throw new Error("Could not prepare content for export.");
        }

        exportWrapper = exportNode.wrapper;
        await sanitizeImageElements(exportNode.clonePage, false);
        stripRiskyBackgroundImages(exportNode.clonePage, false);

        const options = getPdfOptions();

        try {
            await window.html2pdf().set(options).from(exportNode.clonePage).save();
        } catch (firstErr) {
            if (!isUnsupportedImageTypeError(firstErr)) {
                throw firstErr;
            }

            console.warn("Retrying PDF generation after aggressive image sanitization...");
            await sanitizeImageElements(exportNode.clonePage, true);
            stripRiskyBackgroundImages(exportNode.clonePage, true);
            removeCssContentImages(exportNode.clonePage);

            await window.html2pdf().set(options).from(exportNode.clonePage).save();
        }
    } catch (err) {
        console.error("PDF generation failed:", err);
        alert("Could not generate PDF. Please try again.");
    } finally {
        if (exportWrapper && exportWrapper.parentNode) {
            exportWrapper.parentNode.removeChild(exportWrapper);
        }
        btn.disabled = false;
        btn.innerHTML = original;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("downloadPdfBtn");
    fitPdfContentToSinglePage();

    if (btn) {
        btn.addEventListener("click", downloadPdf);
    }

    window.addEventListener("resize", fitPdfContentToSinglePage);
});
