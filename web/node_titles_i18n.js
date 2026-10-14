import { app } from "../../scripts/app.js";
import { no8dLocale, t } from "./no8d_i18n.js";

const NODE_TITLE_KEYS = {
    NO8DLoraStack: "sliderStackTitle",
    NO8DGenerate: "generateTitle",
    NO8DRemoveKrea2ReferenceLatents: "removeKreaReferenceTitle",
    NO8DABPreview: "abPreviewTitle",
    NO8DBatchPromptPlus: "promptNodeTitle",
    NO8DDynamicPrompt: "dynamicPromptNodeTitle",
    NO8DPromptView: "promptViewTitle",
    NO8DLoadImages: "imageLoaderTitle",
    NO8DSaveImageTextDataset: "saveTitle",
    NO8DEmptyLatent: "emptyLatentTitle",
    NO8DImageSize: "imageSizeTitle",
    NO8DImageGrid: "imageGridTitle",
    NO8DImageComposer: "imageComposerTitle",
    NO8DImageTitle: "imageTitleTitle",
    NO8DKreaStyleSelector: "kreaStyleTitle",
};

const NODE_DESCRIPTION_KEYS = {
    NO8DRemoveKrea2ReferenceLatents: "removeKreaReferenceDescription",
    NO8DImageGrid: "imageGridDescription",
    NO8DImageComposer: "imageComposerDescription",
    NO8DImageTitle: "imageTitleDescription",
    NO8DKreaStyleSelector: "kreaStyleDescription",
    NO8DImageSize: "imageSizeDescription",
};

const WIDGET_LABELS = {
    NO8DImageGrid: {
        layout: "imageGridLayout",
        crop_mode: "imageGridCropMode",
        columns: "imageGridColumns",
        spacing: "imageGridSpacing",
        background_color: "imageGridBackground",
    },
    NO8DImageTitle: {
        titles: "imageTitleTitles",
        output_size: "imageTitleOutputSize",
        title_bar_color: "imageTitleBarColor",
        title_bar_opacity: "imageTitleBarOpacity",
        title_position: "imageTitlePosition",
        title_bar_height: "imageTitleBarHeight",
        font_size: "imageTitleFontSize",
        text_padding: "imageTitlePadding",
        text_color: "imageTitleTextColor",
        text_align: "imageTitleTextAlign",
    },
    NO8DImageSize: {
        auto_output: "imageSizeAutoOutput",
        width: "imageSizeTargetWidth",
        height: "imageSizeTargetHeight",
        short_side: "imageSizeShortSide",
        long_side: "imageSizeLongSide",
        interpolation: "imageSizeInterpolation",
        method: "imageSizeMethod",
        condition: "imageSizeCondition",
        multiple_of: "imageSizeMultipleOf",
        force_size: "imageSizeForceSize",
        aspect_ratio: "imageSizeAspectRatio",
        invert_ratio: "imageSizeInvertRatio",
        fill_color: "imageSizeFillColor",
        fill_position: "imageSizeFillPosition",
    },
};

const COMBO_LABELS = {
    NO8DImageGrid: {
        layout: [
            ["imageGridHorizontal", "Horizontal", "横向"],
            ["imageGridVertical", "Vertical", "纵向"],
            ["imageGridGrid", "Grid", "网格"],
        ],
        crop_mode: [
            ["imageGridCropNone", "None", "none"],
            ["imageGridCropStandard", "Standard crop", "标准裁切"],
            ["imageGridCropLeft", "Left crop", "居左裁切"],
            ["imageGridCropCenter", "Center crop", "居中裁切"],
            ["imageGridCropRight", "Right crop", "居右裁切"],
        ],
    },
    NO8DImageTitle: {
        output_size: [
            ["imageTitleOriginalSize", "Original size", "原始尺寸"],
            ["imageTitle1K", "1K", "1K"],
            ["imageTitle2K", "2K", "2K"],
            ["imageTitle4K", "4K", "4K"],
        ],
        title_position: [
            ["imageTitleOutsideTop", "Outside top", "图外顶部"],
            ["imageTitleInsideTop", "Inside top", "图内顶部"],
            ["imageTitleMiddle", "Middle", "中部"],
            ["imageTitleInsideBottom", "Inside bottom", "图内底部"],
            ["imageTitleOutsideBottom", "Outside bottom", "图外底部"],
        ],
        text_align: [
            ["imageTitleAlignLeft", "Left", "居左"],
            ["imageTitleAlignCenter", "Center", "居中"],
            ["imageTitleAlignRight", "Right", "居右"],
        ],
    },
    NO8DImageSize: {
        interpolation: [
            ["imageSizeNearest", "nearest", "最近邻"],
            ["imageSizeBilinear", "bilinear", "双线性"],
            ["imageSizeBicubic", "bicubic", "双三次"],
            ["imageSizeArea", "area", "区域"],
            ["imageSizeNearestExact", "nearest-exact", "精确最近邻"],
            ["imageSizeLanczos", "lanczos", "兰索斯"],
        ],
        method: [
            ["imageSizeStretch", "stretch", "拉伸"],
            ["imageSizeCrop", "crop", "裁切"],
            ["imageSizePad", "pad", "填充"],
        ],
        condition: [
            ["imageSizeAlways", "always", "总是"],
            ["imageSizeDownscaleIfBigger", "downscale if bigger", "仅在原图较大时缩小"],
            ["imageSizeUpscaleIfSmaller", "upscale if smaller", "仅在原图较小时放大"],
            ["imageSizeIfBiggerArea", "if bigger area", "仅在原图面积较大时"],
            ["imageSizeIfSmallerArea", "if smaller area", "仅在原图面积较小时"],
        ],
        aspect_ratio: [
            ["imageSizeOriginalRatio", "original", "原图比例"],
            ["imageSizeRatio1x1", "1:1", "1:1"],
            ["imageSizeRatio1x2", "1:2", "1:2"],
            ["imageSizeRatio2x3", "2:3", "2:3"],
            ["imageSizeRatio3x4", "3:4", "3:4"],
            ["imageSizeRatio4x5", "4:5", "4:5"],
            ["imageSizeRatio9x16", "9:16", "9:16"],
            ["imageSizeRatio9x21", "9:21", "9:21"],
        ],
        fill_position: [
            ["imageSizePositionCenter", "center", "居中"],
            ["imageSizePositionTop", "top", "顶部"],
            ["imageSizePositionBottom", "bottom", "底部"],
            ["imageSizePositionLeft", "left", "左侧"],
            ["imageSizePositionRight", "right", "右侧"],
            ["imageSizePositionTopLeft", "top-left", "左上"],
            ["imageSizePositionTopRight", "top-right", "右上"],
            ["imageSizePositionBottomLeft", "bottom-left", "左下"],
            ["imageSizePositionBottomRight", "bottom-right", "右下"],
        ],
    },
};

const INPUT_LABELS = {
    NO8DImageTitle: { images: "imageTitleImages" },
    NO8DImageSize: { image: "imageSizeImage" },
};

const OUTPUT_LABELS = {
    NO8DImageComposer: {
        image: "imageComposerImage",
        width: "imageComposerWidth",
        height: "imageComposerHeight",
    },
    NO8DImageSize: {
        image: "imageSizeImage",
        width: "imageSizeWidth",
        height: "imageSizeHeight",
    },
};

const PERCENT_WIDGETS = new Set(["title_bar_opacity", "title_bar_height"]);
const COLOR_WIDGETS = {
    NO8DImageGrid: new Set(["background_color"]),
    NO8DImageTitle: new Set(["title_bar_color", "text_color"]),
};
const PERCENT_DISPLAY = Symbol("no8dPercentDisplay");
const PENDING_REFRESH = new WeakSet();

function applyPercentDisplay(widget) {
    if (!PERCENT_WIDGETS.has(widget.name) || widget[PERCENT_DISPLAY]) return false;
    Object.defineProperty(widget, "_displayValue", {
        configurable: true,
        get() {
            const precision = this.options?.precision ?? 0;
            return `${Number(this.value).toFixed(precision)}%`;
        },
    });
    widget[PERCENT_DISPLAY] = true;
    return true;
}

function removeDuplicateColorControls(node, className) {
    const colorNames = COLOR_WIDGETS[className];
    if (!colorNames) return false;
    let changed = false;
    const seen = new Set();
    for (let index = 0; index < (node.widgets || []).length; ) {
        const widget = node.widgets[index];
        if (!colorNames.has(widget.name)) {
            index++;
            continue;
        }
        if (!seen.has(widget.name)) {
            seen.add(widget.name);
            index++;
            continue;
        }
        widget.onRemove?.();
        widget.element?.remove?.();
        node.widgets.splice(index, 1);
        changed = true;
    }
    const widgetNames = new Set(
        (node.widgets || []).filter((widget) => colorNames.has(widget.name)).map((widget) => widget.name),
    );
    for (let index = (node.inputs || []).length - 1; index >= 0; index--) {
        const input = node.inputs[index];
        if (!widgetNames.has(input.name) || String(input.type).toUpperCase() !== "COLOR") continue;
        if (node.removeInput) node.removeInput(index);
        else node.inputs.splice(index, 1);
        changed = true;
    }
    return changed;
}

let activeLocale = "";

function nodeClass(node) {
    return node?.comfyClass || node?.constructor?.comfyClass || node?.type || "";
}

function titleForClass(className) {
    const key = NODE_TITLE_KEYS[className];
    return key ? t(key) : "";
}

function normalizedComboValue(value) {
    return String(value ?? "").trim().toLocaleLowerCase().replace(/[\s\-_/]+/g, "");
}

function migrateImageSizeCombo(widgetName, value) {
    if (widgetName !== "method") return value;
    const token = normalizedComboValue(value);
    if (["fillcrop", "keepproportion", "保持比例"].includes(token)) return "crop";
    if (["补边"].includes(token)) return "pad";
    return value;
}

function scheduleNodeRefresh(node) {
    if (!node || PENDING_REFRESH.has(node)) return;
    PENDING_REFRESH.add(node);
    setTimeout(() => {
        PENDING_REFRESH.delete(node);
        if (!applyNodeTitle(node)) return;
        node.graph?.setDirtyCanvas?.(true, true);
        app?.canvas?.setDirty?.(true, true);
    }, 100);
}

function applyNodeTitle(node) {
    const className = nodeClass(node);
    const title = titleForClass(className);
    let changed = removeDuplicateColorControls(node, className);
    if (title && node.title !== title) {
        node.title = title;
        changed = true;
    }
    const widgetLabels = WIDGET_LABELS[className] || {};
    const comboLabels = COMBO_LABELS[className] || {};
    for (const widget of node.widgets || []) {
        if (className === "NO8DImageTitle") changed = applyPercentDisplay(widget) || changed;
        const labelKey = widgetLabels[widget.name];
        if (labelKey) {
            const label = t(labelKey);
            widget.label = label;
            widget.options = widget.options || {};
            widget.options.label = label;
            changed = true;
        }
        const entries = comboLabels[widget.name];
        if (!entries) continue;
        const current = String(widget.value ?? "");
        const migrated = className === "NO8DImageSize"
            ? migrateImageSizeCombo(widget.name, current)
            : current;
        const normalizedValue = String(migrated ?? "");
        const normalizedCurrent = normalizedComboValue(normalizedValue);
        const entry = entries.find(([, english, chinese]) => (
            normalizedCurrent === normalizedComboValue(english)
            || normalizedCurrent === normalizedComboValue(chinese)
        ));
        const canonicalIndex = className === "NO8DImageSize" ? 1 : 2;
        if (entry) widget.value = entry[canonicalIndex];
        else if (className === "NO8DImageTitle" && widget.name === "output_size") {
            widget.value = entries[0][canonicalIndex];
            widget.callback?.(widget.value, app.canvas, node, app.canvas?.graph_mouse);
        }
        widget.options = widget.options || {};
        widget.options.values = entries.map((entry) => entry[canonicalIndex]);
        widget.options.getOptionLabel = (value) => {
            const option = entries.find(([, english, chinese]) => (
                normalizedComboValue(value) === normalizedComboValue(english)
                || normalizedComboValue(value) === normalizedComboValue(chinese)
            ));
            return option ? t(option[0]) : value;
        };
        changed = true;
    }
    const inputLabels = INPUT_LABELS[className] || {};
    for (const input of node.inputs || []) {
        const key = inputLabels[input.name];
        if (!key) continue;
        const label = t(key);
        input.label = label;
        input.localized_name = label;
        changed = true;
    }
    const outputLabels = OUTPUT_LABELS[className] || {};
    for (const output of node.outputs || []) {
        const key = outputLabels[output.name];
        if (!key) continue;
        const label = t(key);
        output.label = label;
        output.localized_name = label;
        changed = true;
    }
    return changed;
}

function applyAllNodeTitles(force = false) {
    const locale = no8dLocale();
    if (!force && locale === activeLocale) return;
    activeLocale = locale;
    let changed = false;
    for (const node of app?.graph?._nodes || []) {
        changed = applyNodeTitle(node) || changed;
    }
    if (changed) {
        app?.graph?.setDirtyCanvas?.(true, true);
        app?.canvas?.setDirty?.(true, true);
    }
}

app.registerExtension({
    name: "NO8D.Control.NodeTitlesI18N",
    async setup() {
        activeLocale = no8dLocale();
        setTimeout(() => applyAllNodeTitles(true), 500);
        window.addEventListener("storage", () => applyAllNodeTitles(true));
        window.addEventListener("languagechange", () => applyAllNodeTitles(true));
    },
    async nodeCreated(node) {
        applyNodeTitle(node);
        scheduleNodeRefresh(node);
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const title = titleForClass(nodeData?.name);
        if (!title) return;
        nodeData.display_name = title;
        nodeData.title = title;
        const descriptionKey = NODE_DESCRIPTION_KEYS[nodeData?.name];
        if (descriptionKey) nodeData.description = t(descriptionKey);
        if (!WIDGET_LABELS[nodeData.name]) return;
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onCreated?.apply(this, arguments);
            applyNodeTitle(this);
            scheduleNodeRefresh(this);
        };
        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            setTimeout(() => {
                if (!applyNodeTitle(this)) return;
                this.graph?.setDirtyCanvas?.(true, true);
                app?.canvas?.setDirty?.(true, true);
            }, 0);
        };
    },
});
