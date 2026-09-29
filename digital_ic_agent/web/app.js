const state = {
    taskKinds: [],
    tasks: [],
    gallery: [],
    stream: null,
    activeScreen: "home",
    activeTaskKind: "digital_ic_workflow",
    selectedTaskId: null,
    taskDetail: null,
    detailOutlineCleanup: null,
    picturesAvailable: false,
    customPortrait: null,
    runtime: null,
    templates: [],
    ready: false,
    auth: {
        enabled: false,
        authenticated: false,
        display_name: null,
        llm_config_saved: false,
        llm_config: null,
    },
};

const portraitFallbackGallery = [
    {
        task_id: "portrait-1",
        title: "Practioner / Night Shift",
        caption: "夜色、玻璃反射和工位灯带出来的城市层次。",
        asset_type: "portrait",
        image_url: "/pictures/1.jpg",
        fallback_scene_url: null,
        is_fallback: true,
    },
    {
        task_id: "portrait-2",
        title: "Practioner / Climb",
        caption: "轻巧但不软，动作感和专注感都很直接。",
        asset_type: "portrait",
        image_url: "/pictures/2.jpg",
        fallback_scene_url: null,
        is_fallback: true,
    },
    {
        task_id: "portrait-3",
        title: "Practioner / Neon Hood",
        caption: "带一点戏剧光，但整体气质仍然克制。",
        asset_type: "portrait",
        image_url: "/pictures/3.jpg",
        fallback_scene_url: null,
        is_fallback: true,
    },
    {
        task_id: "portrait-4",
        title: "Practioner / Mirror Flash",
        caption: "生活感更强的镜面自拍，适合作为首页与封面流里的近景切片。",
        asset_type: "portrait",
        image_url: "/pictures/4.jpg",
        fallback_scene_url: null,
        is_fallback: true,
    },
    {
        task_id: "portrait-5",
        title: "Practioner / Doorway",
        caption: "站姿和门框构图更完整，适合放进滚动背景做人物剪影层次。",
        asset_type: "portrait",
        image_url: "/pictures/5jpg.jpg",
        fallback_scene_url: null,
        is_fallback: true,
    },
    {
        task_id: "portrait-6",
        title: "Practioner / Graduation Walk",
        caption: "毕业场景和花束让画面更开阔，适合做首页主视觉和封面展示。",
        asset_type: "portrait",
        image_url: "/pictures/6.jpg",
        fallback_scene_url: null,
        is_fallback: true,
    },
    {
        task_id: "portrait-7",
        title: "Practioner / Field Moment",
        caption: "坐姿和草地背景能拉开节奏，适合补足画廊里的横向氛围。",
        asset_type: "portrait",
        image_url: "/pictures/7.jpg",
        fallback_scene_url: null,
        is_fallback: true,
    },
];

document.addEventListener("DOMContentLoaded", () => {
    initializePortraitTheme();
    bindEvents();
    void initializeApp();
});

async function initializeApp() {
    setReadyState(false);
    renderAuthPanel();
    try {
        await loadAuthSession();
        await loadRuntime();
        await refreshAll();
        if (canAccessWorkspace()) {
            connectTaskStream();
        }
    } finally {
        setReadyState(true);
        renderAuthPanel();
        switchScreen(state.activeScreen);
    }
}

function bindEvents() {
    const authForm = document.getElementById("auth-form");
    const logoutButton = document.getElementById("logout-button");
    const llmConfigForm = document.getElementById("llm-config-form");
    if (authForm) {
        authForm.addEventListener("submit", (event) => {
            void handleLoginSubmit(event);
        });
    }
    if (logoutButton) {
        logoutButton.addEventListener("click", () => {
            void handleLogout();
        });
    }
    if (llmConfigForm) {
        llmConfigForm.addEventListener("submit", (event) => {
            void handleLlmConfigSubmit(event);
        });
    }
    const portraitUpload = document.getElementById("portrait-upload");
    const portraitReset = document.getElementById("portrait-reset");
    if (portraitUpload) {
        portraitUpload.addEventListener("change", (event) => {
            void handlePortraitUpload(event);
        });
    }
    if (portraitReset) {
        portraitReset.addEventListener("click", resetPortraitTheme);
    }
    document.getElementById("task-form").addEventListener("submit", (event) => {
        void submitTask(event);
    });
    document.getElementById("task-kind").addEventListener("change", (event) => {
        handleTaskKindChange(event);
    });
    document.getElementById("refresh-button").addEventListener("click", () => {
        void refreshAll();
    });
    document.getElementById("phase1-demo-button").addEventListener("click", () => {
        void runPhase1Demo();
    });
    document.getElementById("competition-benchmark-button").addEventListener("click", () => {
        void runCompetitionBenchmark();
    });
    document.getElementById("run-next-button").addEventListener("click", () => {
        void runNextTask();
    });
    document.getElementById("task-feed").addEventListener("click", (event) => {
        void handleTaskFeedClick(event);
    });
    document.getElementById("task-feed").addEventListener("submit", (event) => {
        void handleTaskFeedSubmit(event);
    });
    document.getElementById("task-detail").addEventListener("click", (event) => {
        void handleTaskDetailClick(event);
    });
    document.getElementById("gallery-track").addEventListener("click", (event) => {
        void handleGalleryClick(event);
    });
    document.getElementById("template-library-list").addEventListener("submit", (event) => {
        void handleTemplateInstantiate(event);
    });
    document.addEventListener("click", (event) => {
        handleNavigationClick(event);
    });
}

const portraitStorageKey = "siliconforge.customPortrait.v1";

function initializePortraitTheme() {
    try {
        state.customPortrait = window.localStorage.getItem(portraitStorageKey);
    } catch (error) {
        console.warn("portrait storage is unavailable", error);
    }
    applyPortraitTheme(state.customPortrait);
}

async function handlePortraitUpload(event) {
    const input = event.target;
    const file = input.files?.[0];
    if (!file) return;
    const status = document.getElementById("portrait-status");
    try {
        if (!file.type.startsWith("image/")) {
            throw new Error("请选择 JPG、PNG 或 WebP 图片。");
        }
        if (file.size > 12 * 1024 * 1024) {
            throw new Error("原始图片请控制在 12 MB 以内。");
        }
        if (status) status.textContent = "正在优化照片并生成个人主题…";
        const dataUrl = await createPortraitDataUrl(file);
        state.customPortrait = dataUrl;
        try {
            window.localStorage.setItem(portraitStorageKey, dataUrl);
        } catch (error) {
            console.warn("portrait could not be persisted", error);
        }
        applyPortraitTheme(dataUrl);
        if (status) status.textContent = "个人主题已启用：主视觉与 3D 旋转背景均已更新。";
    } catch (error) {
        if (status) status.textContent = error.message || "照片处理失败，请换一张图片重试。";
    } finally {
        input.value = "";
    }
}

function resetPortraitTheme() {
    state.customPortrait = null;
    try {
        window.localStorage.removeItem(portraitStorageKey);
    } catch (error) {
        console.warn("portrait storage reset failed", error);
    }
    applyPortraitTheme(null);
    const status = document.getElementById("portrait-status");
    if (status) status.textContent = "已恢复项目默认人物形象与 3D 相册背景。";
}

function applyPortraitTheme(dataUrl) {
    const photo = document.getElementById("profile-photo");
    const hasCustomPortrait = Boolean(dataUrl);
    document.body.classList.toggle("has-custom-portrait", hasCustomPortrait);
    if (hasCustomPortrait) {
        document.documentElement.style.setProperty("--custom-portrait", `url("${dataUrl}")`);
        if (photo) photo.src = dataUrl;
    } else {
        document.documentElement.style.removeProperty("--custom-portrait");
        if (photo) photo.src = "/pictures/1.jpg";
    }
}

function createPortraitDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error("无法读取这张图片。"));
        reader.onload = () => {
            const image = new Image();
            image.onerror = () => reject(new Error("图片格式无法解析。"));
            image.onload = () => {
                const maxEdge = 1600;
                const scale = Math.min(1, maxEdge / Math.max(image.naturalWidth, image.naturalHeight));
                const width = Math.max(1, Math.round(image.naturalWidth * scale));
                const height = Math.max(1, Math.round(image.naturalHeight * scale));
                const canvas = document.createElement("canvas");
                canvas.width = width;
                canvas.height = height;
                const context = canvas.getContext("2d");
                context.drawImage(image, 0, 0, width, height);
                resolve(canvas.toDataURL("image/jpeg", 0.86));
            };
            image.src = String(reader.result);
        };
        reader.readAsDataURL(file);
    });
}

async function refreshAll() {
    try {
        await loadAuthSession();
        await loadTaskKinds();
        await loadTemplates();
        if (!canAccessWorkspace()) {
            teardownWorkspace("登录后可查看你自己的任务队列与实时详情。", { keepGallery: true });
            return;
        }
        await loadDashboardSnapshot();
        if (state.selectedTaskId) {
            await loadTaskDetail(state.selectedTaskId, { silent: true });
        }
    } catch (error) {
        reportError(error);
    }
}

async function loadTaskKinds() {
    state.taskKinds = await fetchJson("/api/task-kinds");
    if (!state.taskKinds.some((item) => item.key === state.activeTaskKind)) {
        state.activeTaskKind = state.taskKinds[0]?.key || state.activeTaskKind;
    }
    renderTaskKindSelect();
    renderTaskKindCards();
    renderFlowStudio();
    renderNavigationState();
    renderGallery();
}

async function loadAuthSession() {
    state.auth = await fetchJson("/api/auth/session");
    renderAuthPanel();
}

async function loadDashboardSnapshot() {
    const snapshot = await fetchJson("/api/dashboard");
    applyDashboardSnapshot(snapshot);
}

async function loadRuntime() {
    if (!canAccessWorkspace()) {
        return;
    }
    state.runtime = await fetchJson("/api/runtime");
    renderRuntime();
}

async function loadTemplates() {
    if (!canAccessWorkspace()) {
        state.templates = [];
        renderTemplateLibrary();
        return;
    }
    state.templates = await fetchJson("/api/templates");
    renderTemplateLibrary();
}

function renderRuntime() {
    const runtime = state.runtime;
    if (!runtime) {
        return;
    }
    const gpuDevices = runtime.gpu?.devices || [];
    document.getElementById("runtime-platform").textContent = `${runtime.platform.system} · ${runtime.platform.machine}`;
    document.getElementById("runtime-model").textContent = runtime.model?.name || "未配置";
    document.getElementById("runtime-gpu").textContent = gpuDevices.length
        ? gpuDevices.map((device) => device.name).join(" / ")
        : "开发机 / 远程 API";
    document.getElementById("runtime-eda").textContent = runtime.eda?.ready ? "Icarus + Yosys Ready" : "等待工具链";
}

function renderTaskKindSelect() {
    const select = document.getElementById("task-kind");
    select.innerHTML = state.taskKinds
        .map((item) => `<option value="${escapeHtml(item.key)}">${escapeHtml(item.title)}</option>`)
        .join("");
    if (state.taskKinds.length) {
        select.value = state.activeTaskKind;
    }
}

function renderTaskKindCards() {
    const container = document.getElementById("task-kind-list");
    container.innerHTML = state.taskKinds
        .map(
            (item) => `
                <article class="kind-card ${item.key === state.activeTaskKind ? "is-active" : ""}">
                    <div class="kind-card__head">
                        <p class="task-kind-label">${escapeHtml(formatExecutionStrategy(item.execution_strategy))}</p>
                        <h3>${escapeHtml(item.title)}</h3>
                    </div>
                    <p class="kind-card__summary">${escapeHtml(item.description)}</p>
                    <p class="kind-card__hint">${escapeHtml(item.input_hint)}</p>
                    <button class="secondary-button kind-launch-button" type="button" data-flow-key="${escapeHtml(item.key)}">进入流程</button>
                </article>
            `,
        )
        .join("");
}

function handleNavigationClick(event) {
    const trigger = event.target.closest("[data-screen], [data-flow-key]");
    if (!trigger) {
        return;
    }

    if (trigger.dataset.flowKey) {
        openFlowStudio(trigger.dataset.flowKey);
        return;
    }

    if (trigger.dataset.screen) {
        switchScreen(trigger.dataset.screen);
    }
}

function handleTaskKindChange(event) {
    state.activeTaskKind = resolveTaskKindKey(event.target.value);
    renderTaskKindCards();
    renderFlowStudio();
    renderNavigationState();
}

function openFlowStudio(taskKind) {
    state.activeTaskKind = resolveTaskKindKey(taskKind);
    renderTaskKindCards();
    renderFlowStudio();
    switchScreen("studio");
}

function switchScreen(screenKey) {
    const nextScreen = ["home", "studio", "workspace", "library"].includes(screenKey) ? screenKey : "home";
    state.activeScreen = nextScreen;
    document.body.dataset.activeScreen = nextScreen;
    document.querySelectorAll(".screen").forEach((section) => {
        const isActive = section.id === `screen-${nextScreen}`;
        section.hidden = !isActive;
        section.classList.toggle("is-active", isActive);
    });
    renderNavigationState();
}

function renderNavigationState() {
    document.querySelectorAll(".view-tab").forEach((button) => {
        const isActive = button.dataset.screen
            ? button.dataset.screen === state.activeScreen
            : state.activeScreen === "studio" && button.dataset.flowKey === state.activeTaskKind;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", String(isActive));
    });
}

function renderFlowStudio() {
    const taskKind = getActiveTaskKind();
    if (!taskKind) {
        return;
    }

    state.activeTaskKind = taskKind.key;
    document.getElementById("flow-kicker").textContent = formatExecutionStrategy(taskKind.execution_strategy);
    document.getElementById("flow-title").textContent = taskKind.title;
    document.getElementById("flow-description").textContent = taskKind.description;
    document.getElementById("task-kind").value = taskKind.key;
    const isFullWorkflow = taskKind.key === "digital_ic_workflow";
    const isWorkflowBacked = ["digital_ic_workflow", "rtl_module_generation", "tb_repair"].includes(taskKind.key);
    const requirementInput = document.getElementById("requirement-text");
    const requirementLabel = document.getElementById("requirement-label");
    const requirementHelp = document.getElementById("requirement-help");
    const workflowGuide = document.getElementById("workflow-input-guide");
    const submitButton = document.getElementById("submit-task-button");

    requirementInput.placeholder = isFullWorkflow
        ? "把完整赛题原文粘贴到这里。接口、时序、复位、边界条件和验证方案由 Agent 自动分析。"
        : taskKind.input_hint;
    requirementLabel.textContent = isFullWorkflow ? "赛题原文（唯一必填）" : "任务描述";
    requirementHelp.textContent = isFullWorkflow
        ? "无需手工填写接口契约，也无需先准备 RTL 或测试平台。"
        : taskKind.input_hint;
    workflowGuide.hidden = !isFullWorkflow;
    submitButton.textContent = isFullWorkflow ? "一键启动完整闭环" : `提交${taskKind.title}`;
    document.getElementById("advanced-inputs").classList.toggle("advanced-box--secondary", isWorkflowBacked);
    document.querySelector("#screen-studio .panel-form h2").textContent = `提交 ${taskKind.title} 任务`;
    document.getElementById("flow-highlights").innerHTML = [
        ["执行策略", formatExecutionStrategy(taskKind.execution_strategy)],
        ["输入提示", taskKind.input_hint],
        ["画廊标题", taskKind.gallery_title],
        ["流程说明", taskKind.gallery_caption],
    ]
        .map(
            ([label, value]) => `
                <article class="flow-highlight-card">
                    <span>${escapeHtml(label)}</span>
                    <strong>${escapeHtml(value)}</strong>
                </article>
            `,
        )
        .join("");
}

function renderTemplateLibrary() {
    const container = document.getElementById("template-library-list");
    const count = document.getElementById("template-count");
    if (!container || !count) return;
    count.textContent = String(state.templates.length);
    if (!state.templates.length) {
        container.innerHTML = `<div class="empty-state">当前没有可用模板。完成并验证一个任务后，可在工作台中将其加入个人模板库。</div>`;
        return;
    }
    container.innerHTML = state.templates.map((template) => `
        <article class="template-card">
            <div class="template-card__head">
                <div>
                    <p class="task-kind-label">${escapeHtml(template.category || "通用设计")}</p>
                    <h3>${escapeHtml(template.title)}</h3>
                </div>
                <span class="template-source">${escapeHtml(template.source || "模板")}</span>
            </div>
            <p>${escapeHtml(template.description || "")}</p>
            <p class="template-verification">验证方式：${escapeHtml(template.verification || "实例化后重新验证")}</p>
            <form class="template-form" data-template-id="${escapeHtml(template.template_id)}">
                <div class="template-parameter-grid">
                    ${(template.parameters || []).map((parameter) => `
                        <label>
                            <span>${escapeHtml(parameter.label || parameter.name)}</span>
                            <input type="number" name="${escapeHtml(parameter.name)}" value="${escapeHtml(String(parameter.default ?? ""))}"
                                min="${escapeHtml(String(parameter.minimum ?? ""))}" max="${escapeHtml(String(parameter.maximum ?? ""))}" required>
                        </label>
                    `).join("") || `<p class="field-help">固定模板，没有可调参数。</p>`}
                </div>
                <label>
                    <span>任务标题（选填）</span>
                    <input type="text" name="template-title" placeholder="默认使用模板名称">
                </label>
                <button class="primary-button" type="submit">零 Token 实例化并验证</button>
            </form>
        </article>
    `).join("");
}

async function handleTemplateInstantiate(event) {
    const form = event.target.closest(".template-form");
    if (!form) return;
    event.preventDefault();
    const template = state.templates.find((item) => item.template_id === form.dataset.templateId);
    if (!template) return;
    const button = form.querySelector('button[type="submit"]');
    const parameters = {};
    (template.parameters || []).forEach((parameter) => {
        parameters[parameter.name] = Number(form.elements[parameter.name].value);
    });
    try {
        button.disabled = true;
        button.textContent = "正在实例化并运行 EDA…";
        const response = await fetchJson(`/api/templates/${encodeURIComponent(template.template_id)}/instantiate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title: form.elements["template-title"].value.trim() || null,
                parameters,
            }),
        });
        await refreshAll();
        switchScreen("workspace");
        await loadTaskDetail(response.record.task_id, { navigate: false });
        setLiveIndicator("模板实例化完成，模型 Token 消耗为 0", "live");
    } catch (error) {
        reportError(error);
    } finally {
        button.disabled = false;
        button.textContent = "零 Token 实例化并验证";
    }
}

function getActiveTaskKind() {
    return state.taskKinds.find((item) => item.key === state.activeTaskKind) || state.taskKinds[0] || null;
}

function resolveTaskKindKey(taskKind) {
    return state.taskKinds.find((item) => item.key === taskKind)?.key || state.activeTaskKind || "digital_ic_workflow";
}

function renderGallery() {
    const sourceItems = buildGallerySourceItems();
    const galleryItems = sourceItems.length ? [...sourceItems, ...sourceItems] : [];
    const track = document.getElementById("gallery-track");
    if (!galleryItems.length) {
        track.innerHTML = "";
        return;
    }
    track.innerHTML = galleryItems
        .map(
            (item, index) => {
                const fallbackImage = resolvePortraitFallback(index);
                const primaryImage = resolveGalleryImage(item, index);
                return `
                <article class="gallery-card ${item.task_id === state.selectedTaskId ? "is-selected" : ""} ${item.is_fallback ? "gallery-card--portrait" : ""}" ${item.is_fallback ? "" : `data-gallery-task-id="${escapeHtml(item.task_id)}"`}>
                    <img class="gallery-image" src="${escapeHtml(primaryImage)}" alt="${escapeHtml(item.title)}" onerror="this.onerror=null;this.src='${escapeHtml(fallbackImage)}';">
                    <h3>${escapeHtml(item.title)}</h3>
                    <p>${escapeHtml(item.caption || item.task_kind_title)}</p>
                    <span class="gallery-badge">${escapeHtml(item.asset_type || item.task_kind_title)}</span>
                </article>
            `;
            },
        )
        .join("");
}

function buildGallerySourceItems() {
    const taskItems = state.gallery || [];
    const portraitItems = state.picturesAvailable ? portraitFallbackGallery : [];

    if (!taskItems.length) {
        return portraitItems;
    }
    if (!portraitItems.length) {
        return taskItems;
    }

    const mixedItems = [];
    const cycleLength = Math.max(taskItems.length, portraitItems.length);
    for (let index = 0; index < cycleLength; index += 1) {
        if (taskItems[index]) {
            mixedItems.push(taskItems[index]);
        }
        if (portraitItems.length) {
            mixedItems.push(portraitItems[index % portraitItems.length]);
        }
    }
    return mixedItems;
}

function resolveGalleryImage(item, index) {
    if (item.image_url && (!item.is_fallback || state.picturesAvailable)) {
        return item.image_url;
    }
    return resolvePortraitFallback(index) || item.fallback_scene_url || "/assets/scene-1.svg";
}

function resolvePortraitFallback(index) {
    if (state.picturesAvailable) {
        return portraitFallbackGallery[index % portraitFallbackGallery.length]?.image_url || "/assets/scene-1.svg";
    }
    return `/assets/scene-${(index % 4) + 1}.svg`;
}

async function probePortraitAvailability() {
    for (const item of portraitFallbackGallery) {
        try {
            const response = await fetch(item.image_url, { method: "HEAD" });
            if (response.ok) {
                return true;
            }
        } catch (error) {
            console.warn("portrait probe failed", item.image_url, error);
        }
    }
    return false;
}

function renderAuthPanel() {
    const authStatus = document.getElementById("auth-status");
    const llmStatus = document.getElementById("llm-config-status");
    if (!authStatus || !llmStatus) {
        return;
    }
    const authEnabled = Boolean(state.auth?.enabled);
    const authenticated = canAccessWorkspace();
    const llmConfig = state.auth?.llm_config || null;

    if (state.auth?.display_name) {
        document.getElementById("display-name").value = state.auth.display_name;
    }
    if (llmConfig?.base_url) {
        document.getElementById("user-base-url").value = llmConfig.base_url;
    }
    if (llmConfig?.model) {
        document.getElementById("user-model").value = llmConfig.model;
    }
    document.getElementById("user-transport").value = llmConfig?.llm_transport || "auto";
    document.getElementById("user-api-key").value = "";

    document.getElementById("access-password").disabled = !authEnabled;
    document.getElementById("display-name").disabled = !authEnabled;
    document.getElementById("login-button").disabled = !authEnabled;
    document.getElementById("logout-button").disabled = !authEnabled || !authenticated;
    setFormDisabled(document.getElementById("llm-config-form"), !state.ready || (authEnabled && !authenticated));
    setFormDisabled(document.getElementById("task-form"), !state.ready || (authEnabled && !authenticated));
    document.getElementById("run-next-button").disabled = !state.ready || (authEnabled && !authenticated);
    document.getElementById("phase1-demo-button").disabled = !state.ready || (authEnabled && !authenticated);
    document.getElementById("competition-benchmark-button").disabled = !state.ready || (authEnabled && !authenticated);
    document.getElementById("refresh-button").disabled = !state.ready;

    if (!authEnabled) {
        setStatusMessage(authStatus, "当前服务未开启登录。本地运行时默认沿用服务端 .env 中的全局模型配置。", "local");
        setStatusMessage(llmStatus, "本地调试模式下不启用个人 API 会话保存；部署到外网时，开启访问口令即可切到登录模式。", "local");
        return;
    }

    if (!authenticated) {
        setStatusMessage(authStatus, "当前服务要求先登录后才能看到你自己的任务、详情和实时队列。", "warning");
        setStatusMessage(llmStatus, "登录后，把你自己的 API Key、Base URL 和模型名保存到当前会话；之后的提交、重试和 run-next 都会直接使用你的配置。", "warning");
        return;
    }

    setStatusMessage(authStatus, `已登录：${state.auth.display_name}。当前页面只显示属于这个会话的任务与详情。`, "ready");
    if (state.auth.llm_config_saved && llmConfig) {
        const modelLabel = llmConfig.model || "沿用服务端默认模型";
        const transportLabel = llmConfig.llm_transport || "auto";
        setStatusMessage(
            llmStatus,
            `个人 API 配置已保存：${llmConfig.api_key_hint || "***"} | model=${modelLabel} | transport=${transportLabel}${llmConfig.base_url ? ` | base_url=${llmConfig.base_url}` : ""}`,
            "ready",
        );
    } else {
        setStatusMessage(llmStatus, "你已经登录，但还没有保存个人 API 配置。非 dry-run 任务会在提交或执行前要求先补齐。", "warning");
    }
}

function setStatusMessage(element, text, tone) {
    element.textContent = text;
    element.className = `account-status account-status--${tone}`;
}

function setFormDisabled(form, disabled) {
    if (!form) {
        return;
    }
    form.querySelectorAll("input, textarea, select, button").forEach((element) => {
        element.disabled = disabled;
    });
}

function canAccessWorkspace() {
    return !state.auth?.enabled || Boolean(state.auth?.authenticated);
}

function teardownWorkspace(message, options = {}) {
    if (state.stream) {
        state.stream.close();
        state.stream = null;
    }
    state.tasks = [];
    if (!options.keepGallery) {
        state.gallery = [];
    }
    state.selectedTaskId = null;
    state.taskDetail = null;
    renderGallery();
    renderTaskFeed();
    renderTaskDetailEmpty(message || "登录后可查看任务详情。", { authLocked: true });
    setLiveIndicator(message || "登录后可连接实时通道", "idle");
}

async function handleLoginSubmit(event) {
    event.preventDefault();
    if (!state.auth?.enabled) {
        return;
    }

    try {
        setReadyState(false);
        renderAuthPanel();
        state.auth = await fetchJson("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                display_name: valueOf("display-name"),
                password: document.getElementById("access-password").value,
            }),
        });
        document.getElementById("access-password").value = "";
        renderAuthPanel();
        await refreshAll();
        setReadyState(true);
        renderAuthPanel();
        connectTaskStream();
    } catch (error) {
        setReadyState(true);
        renderAuthPanel();
        reportError(error);
    }
}

async function handleLogout() {
    try {
        await fetchJson("/api/auth/logout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        state.auth = await fetchJson("/api/auth/session");
        renderAuthPanel();
        teardownWorkspace("你已经退出登录。重新登录后才能继续查看自己的任务。", { keepGallery: true });
    } catch (error) {
        reportError(error);
    }
}

async function handleLlmConfigSubmit(event) {
    event.preventDefault();
    if (!state.auth?.enabled || !state.auth?.authenticated) {
        reportError(new Error("请先登录后再保存个人 API 配置。"));
        return;
    }

    try {
        state.auth = await fetchJson("/api/auth/llm-config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                api_key: document.getElementById("user-api-key").value,
                base_url: valueOf("user-base-url") || null,
                model: valueOf("user-model") || null,
                llm_transport: valueOf("user-transport") || "auto",
            }),
        });
        renderAuthPanel();
    } catch (error) {
        reportError(error);
    }
}

function renderTaskFeed() {
    const feed = document.getElementById("task-feed");
    if (!canAccessWorkspace()) {
        feed.innerHTML = `<div class="empty-state">登录后可查看你自己的任务队列、取消/重试按钮和封面上传区域。</div>`;
        return;
    }
    if (!state.tasks.length) {
        feed.innerHTML = `<div class="empty-state">还没有任务。你可以先提交一个模块生成、EDA triage 或接口契约校验任务。</div>`;
        return;
    }

    const existingCards = new Map(
        Array.from(feed.querySelectorAll(".task-card[data-task-id]"), (node) => [node.dataset.taskId, node]),
    );
    const orderedNodes = state.tasks.map((task) => {
        const existing = existingCards.get(task.status.task_id);
        if (!existing) {
            return createTaskCardElement(task);
        }
        syncTaskCardElement(existing, task);
        existingCards.delete(task.status.task_id);
        return existing;
    });

    feed.replaceChildren(...orderedNodes);

    refreshSelectionState();
}

function createTaskCardElement(task) {
    const template = document.getElementById("task-card-template");
    const article = template.content.firstElementChild.cloneNode(true);
    article.dataset.taskId = task.status.task_id;
    if (task.status.task_id === state.selectedTaskId) {
        article.classList.add("is-selected");
    }

    article.querySelector(".task-kind-label").textContent = task.status.task_kind_title;
    article.querySelector(".task-title").textContent = task.status.title;
    article.querySelector(".task-meta").textContent = `${formatMode(task.status.mode)} | ${formatOrigin(task.status.origin)} | ${task.status.output_dir}`;
    article.querySelector(".task-actions").innerHTML = buildTaskActionButtons(task);
    article.querySelector(".progress-stage").textContent = task.progress.stage_label;
    article.querySelector(".progress-percent").textContent = `${task.progress.percent}%`;

    const statusBadge = article.querySelector(".status-badge");
    statusBadge.textContent = formatTaskStatus(task.status);
    statusBadge.classList.add(`status-${task.status.status}`);
    article.querySelector(".progress-fill").style.width = `${task.progress.percent}%`;

    article.querySelector(".eda-summary").innerHTML = buildEdaSummary(task.eda_summary);
    article.querySelector(".repair-history").innerHTML = buildRepairHistory(task.repair_history);
    article.querySelector(".asset-list").innerHTML = buildAssetList(task.cover_assets, task.status.task_id);

    const uploadForm = article.querySelector(".asset-upload-form");
    uploadForm.dataset.taskId = task.status.task_id;
    return article;
}

function buildTaskActionButtons(task) {
    const actions = new Set(task.available_actions || []);
    actions.add("detail");

    const buttons = [
        `<button class="task-action-button" type="button" data-task-action="detail" data-task-id="${escapeHtml(task.status.task_id)}">查看详情</button>`,
    ];

    if (actions.has("cancel")) {
        const cancelLabel = task.status.status === "running" ? "请求取消" : "取消任务";
        buttons.push(
            `<button class="task-action-button task-action-button--danger" type="button" data-task-action="cancel" data-task-id="${escapeHtml(task.status.task_id)}">${cancelLabel}</button>`,
        );
    }

    if (actions.has("retry")) {
        buttons.push(
            `<button class="task-action-button" type="button" data-task-action="retry" data-task-id="${escapeHtml(task.status.task_id)}">重试任务</button>`,
        );
    }

    return buttons.join("");
}

function buildEdaSummary(eda) {
    if (!eda.available) {
        return `<p>EDA 摘要：当前还没有生成 eda_result.json。</p>`;
    }

    const issueList = eda.precheck_issues?.length
        ? `<ul>${eda.precheck_issues.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
        : "";
    const missing = eda.missing_module_definitions?.length
        ? `缺失模块：${escapeHtml(eda.missing_module_definitions.join(", "))}`
        : "缺失模块：无";

    return `
        <p>EDA 摘要：工具=${escapeHtml(eda.tool_backend || "未知")} | 顶层模块=${escapeHtml(eda.top_module || "无")} | 总体=${formatBoolean(eda.overall_pass)}</p>
        <p>simulation=${formatBoolean(eda.simulation_passed)} | synthesis=${formatBoolean(eda.synthesis_passed)} | ${missing}</p>
        ${issueList}
    `;
}

function buildRepairHistory(history) {
    if (!history?.length) {
        return `<p>修复历史：暂无。</p>`;
    }
    return `
        <p>修复历史：</p>
        <ul>
            ${history
                .map(
                    (item) => `<li>Attempt ${item.attempt} · ${escapeHtml(item.label)} · ${escapeHtml(item.summary)}</li>`,
                )
                .join("")}
        </ul>
    `;
}

function buildAssetList(assets, taskId) {
    if (!assets?.length) {
        return `<p>任务封面：暂无。可以上传板卡图、波形截图、日志快照或产物预览图。</p>`;
    }
    return `
        <div class="asset-chip-list">
            ${assets
                .map(
                    (asset) => `
                        <span class="asset-chip">
                            <span>${escapeHtml(asset.asset_type)}${asset.is_cover ? ' · cover' : ''}</span>
                            <button type="button" data-asset-action="cover" data-task-id="${escapeHtml(taskId)}" data-asset-id="${escapeHtml(asset.asset_id)}">设为封面</button>
                        </span>
                    `,
                )
                .join("")}
        </div>
    `;
}

async function submitTask(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submitButton = document.getElementById("submit-task-button");
    try {
        if (!canAccessWorkspace()) {
            throw new Error("请先登录后再提交任务。");
        }
        const payload = {
            title: valueOf("title") || null,
            task_kind: valueOf("task-kind") || "digital_ic_workflow",
            execution: valueOf("execution") || "sync",
            mode: valueOf("mode") || "fpga",
            dry_run: document.getElementById("dry-run").checked,
            output_dir: valueOf("output-dir") || null,
            task_file: valueOf("task-file") || null,
            requirement_text: valueOf("requirement-text") || "",
            metadata: buildMetadata(),
        };

        const workflowBackedKinds = new Set(["digital_ic_workflow", "rtl_module_generation", "tb_repair"]);
        if (workflowBackedKinds.has(payload.task_kind) && !payload.requirement_text && !payload.task_file) {
            if (payload.title) {
                payload.requirement_text = payload.title;
            } else {
                document.getElementById("requirement-text").focus();
                throw new Error("请先粘贴赛题原文。完整闭环会自动完成接口契约、RTL、测试平台、仿真、综合和修复。");
            }
        }

        if (!payload.title && payload.requirement_text) {
            payload.title = payload.requirement_text.split(/\r?\n/)[0].slice(0, 48) || null;
        }

        submitButton.disabled = true;
        submitButton.textContent = payload.execution === "sync" ? "Agent 正在执行完整闭环…" : "正在创建任务…";
        const response = await fetchJson("/api/tasks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        state.activeTaskKind = payload.task_kind;
        form.reset();
        renderFlowStudio();
        switchScreen("workspace");
        if (response.summary) {
            applyTaskUpsert(response.summary, { refreshDetail: false });
        }
        if (response.record?.task_id) {
            await loadTaskDetail(response.record.task_id, { navigate: false });
        }
    } catch (error) {
        reportError(error);
    } finally {
        submitButton.disabled = false;
        renderFlowStudio();
    }
}

async function runNextTask() {
    try {
        if (!canAccessWorkspace()) {
            throw new Error("请先登录后再执行队列。");
        }
        const response = await fetchJson("/api/tasks/run-next", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });

        if (response.status === "executed" && response.summary) {
            applyTaskUpsert(response.summary);
        }
    } catch (error) {
        reportError(error);
    }
}

async function handleTaskFeedClick(event) {
    const taskButton = event.target.closest("[data-task-action]");
    if (taskButton) {
        await handleTaskAction(taskButton.dataset.taskId, taskButton.dataset.taskAction);
        return;
    }

    const assetButton = event.target.closest('[data-asset-action="cover"]');
    if (assetButton) {
        await setTaskCover(assetButton.dataset.taskId, assetButton.dataset.assetId);
    }
}

async function handleTaskFeedSubmit(event) {
    const form = event.target.closest(".asset-upload-form");
    if (!form) {
        return;
    }

    event.preventDefault();
    await uploadTaskAsset(form);
}

async function handleTaskDetailClick(event) {
    const assetButton = event.target.closest('[data-asset-action="cover"]');
    if (assetButton) {
        await setTaskCover(assetButton.dataset.taskId, assetButton.dataset.assetId);
        return;
    }

    const taskButton = event.target.closest("[data-task-action]");
    if (!taskButton) {
        return;
    }

    await handleTaskAction(taskButton.dataset.taskId, taskButton.dataset.taskAction);
}

async function handleGalleryClick(event) {
    const galleryCard = event.target.closest("[data-gallery-task-id]");
    if (!galleryCard) {
        return;
    }

    switchScreen("workspace");
    await loadTaskDetail(galleryCard.dataset.galleryTaskId, { navigate: false });
}

async function handleTaskAction(taskId, action) {
    if (!taskId || !action) {
        return;
    }
    if (!canAccessWorkspace()) {
        reportError(new Error("请先登录后再操作任务。"));
        return;
    }

    if (action === "detail") {
        switchScreen("workspace");
        await loadTaskDetail(taskId, { navigate: false });
        return;
    }

    if (action === "save-template") {
        try {
            await fetchJson(`/api/tasks/${taskId}/save-template`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });
            await loadTemplates();
            setLiveIndicator("设计已加入个人模板库", "live");
            switchScreen("library");
        } catch (error) {
            reportError(error);
        }
        return;
    }

    try {
        const response = await fetchJson(`/api/tasks/${taskId}/${action}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });

        if (response.summary) {
            applyTaskUpsert(response.summary, { refreshDetail: false });
            upsertGalleryFromSummary(response.summary);
        }

        if (action === "retry" && response.record?.task_id) {
            switchScreen("workspace");
            await loadTaskDetail(response.record.task_id, { navigate: false });
        } else if (state.selectedTaskId === taskId) {
            await loadTaskDetail(taskId, { silent: true, navigate: false });
        }
    } catch (error) {
        reportError(error);
    }
}

async function uploadTaskAsset(form) {
    const taskId = form.dataset.taskId;
    const fileInput = form.querySelector(".asset-file-input");
    if (!taskId || !fileInput.files.length) {
        return;
    }
    if (!canAccessWorkspace()) {
        reportError(new Error("请先登录后再上传任务资产。"));
        return;
    }

    try {
        const formData = new FormData();
        formData.append("file", fileInput.files[0]);
        formData.append("asset_type", form.querySelector(".asset-type-select").value);
        formData.append("caption", form.querySelector(".asset-caption-input").value.trim());
        formData.append("is_cover", String(form.querySelector(".asset-cover-checkbox").checked));

        const response = await fetch(`/api/tasks/${taskId}/assets`, {
            method: "POST",
            body: formData,
        });
        if (!response.ok) {
            throw new Error(await response.text());
        }

        const payload = await response.json();
        form.reset();
        if (payload.summary) {
            applyTaskUpsert(payload.summary, { refreshDetail: false });
            upsertGalleryFromSummary(payload.summary);
        }
        if (state.selectedTaskId === taskId) {
            await loadTaskDetail(taskId, { silent: true, navigate: false });
        }
    } catch (error) {
        reportError(error);
    }
}

async function setTaskCover(taskId, assetId) {
    try {
        if (!canAccessWorkspace()) {
            throw new Error("请先登录后再修改封面。");
        }
        const payload = await fetchJson(`/api/tasks/${taskId}/assets/${assetId}/cover`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });

        if (payload.summary) {
            applyTaskUpsert(payload.summary, { refreshDetail: false });
            upsertGalleryFromSummary(payload.summary);
        }
        if (state.selectedTaskId === taskId) {
            await loadTaskDetail(taskId, { silent: true, navigate: false });
        }
    } catch (error) {
        reportError(error);
    }
}

function connectTaskStream() {
    if (state.stream) {
        state.stream.close();
    }
    if (!canAccessWorkspace()) {
        setLiveIndicator("登录后可连接你的实时队列", "idle");
        return;
    }

    const stream = new EventSource("/api/stream/tasks");
    state.stream = stream;
    setLiveIndicator("实时通道连接中", "idle");

    stream.addEventListener("snapshot", (event) => {
        applyDashboardSnapshot(JSON.parse(event.data));
        setLiveIndicator("实时通道已连接", "live");
    });

    stream.addEventListener("task-upsert", (event) => {
        applyTaskUpsert(JSON.parse(event.data));
        setLiveIndicator("实时通道已连接", "live");
    });

    stream.addEventListener("task-remove", (event) => {
        const payload = JSON.parse(event.data);
        applyTaskRemove(payload.task_id);
        setLiveIndicator("实时通道已连接", "live");
    });

    stream.addEventListener("gallery-updated", (event) => {
        const payload = JSON.parse(event.data);
        applyGalleryUpdate(payload.gallery || []);
        setLiveIndicator("实时通道已连接", "live");
    });

    stream.onerror = () => {
        setLiveIndicator("实时通道重连中", "error");
    };
}

function applyDashboardSnapshot(snapshot) {
    state.tasks = sortTasks(snapshot.tasks || []);
    state.gallery = snapshot.gallery || [];
    renderGallery();
    renderTaskFeed();

    if (state.selectedTaskId && !state.tasks.some((task) => task.status.task_id === state.selectedTaskId)) {
        clearTaskDetail();
    }
}

function applyTaskUpsert(task, options = {}) {
    if (!task?.status?.task_id) {
        return;
    }

    upsertTaskSummary(task);
    upsertTaskCard(task);
    refreshSelectionState();

    if (state.selectedTaskId === task.status.task_id && options.refreshDetail !== false) {
        void loadTaskDetail(task.status.task_id, { silent: true, navigate: false });
    }
}

function applyTaskRemove(taskId) {
    state.tasks = state.tasks.filter((task) => task.status.task_id !== taskId);
    renderTaskFeed();
    if (state.selectedTaskId === taskId) {
        clearTaskDetail();
    }
}

function applyGalleryUpdate(gallery) {
    state.gallery = gallery;
    renderGallery();
    refreshSelectionState();
}

function upsertTaskSummary(task) {
    const index = state.tasks.findIndex((item) => item.status.task_id === task.status.task_id);
    if (index >= 0) {
        state.tasks[index] = task;
    } else {
        state.tasks.push(task);
    }
    state.tasks = sortTasks(state.tasks);
}

function upsertTaskCard(task) {
    const feed = document.getElementById("task-feed");
    const existing = feed.querySelector(`[data-task-id="${task.status.task_id}"]`);

    if (!existing) {
        renderTaskFeed();
        return;
    }

    syncTaskCardElement(existing, task);
}

function syncTaskCardElement(target, task) {
    const replacement = createTaskCardElement(task);
    target.className = replacement.className;
    target.dataset.taskId = replacement.dataset.taskId;
    target.innerHTML = replacement.innerHTML;
}

function upsertGalleryFromSummary(summary) {
    const coverAsset = getCoverAsset(summary.cover_assets || []);
    if (!coverAsset) {
        return;
    }

    const galleryItem = {
        task_id: summary.status.task_id,
        title: summary.status.title,
        task_kind_title: summary.status.task_kind_title,
        image_url: coverAsset.url,
        caption: coverAsset.caption || summary.status.task_kind_title,
        asset_type: coverAsset.asset_type,
        fallback_scene_url: null,
    };

    const index = state.gallery.findIndex((item) => item.task_id === summary.status.task_id);
    if (index >= 0) {
        state.gallery[index] = galleryItem;
    } else {
        state.gallery.unshift(galleryItem);
    }
    renderGallery();
    refreshSelectionState();
}

async function loadTaskDetail(taskId, options = {}) {
    if (!canAccessWorkspace()) {
        renderTaskDetailEmpty("登录后可查看任务详情。", { authLocked: true });
        return;
    }
    if (options.navigate !== false) {
        switchScreen("workspace");
    }
    state.selectedTaskId = taskId;
    refreshSelectionState();
    if (!options.silent) {
        renderTaskDetailLoading();
    }

    try {
        const payload = await fetchJson(`/api/tasks/${taskId}/detail`);
        if (state.selectedTaskId !== taskId) {
            return;
        }

        state.taskDetail = payload;
        if (payload.summary) {
            applyTaskUpsert(payload.summary, { refreshDetail: false });
        }
        renderTaskDetail();
    } catch (error) {
        if (state.selectedTaskId === taskId) {
            renderTaskDetailError(error);
        }
        reportError(error, false);
    }
}

function clearTaskDetail() {
    state.selectedTaskId = null;
    state.taskDetail = null;
    renderTaskDetailEmpty();
    refreshSelectionState();
}

function renderTaskDetail() {
    const container = document.getElementById("task-detail");
    if (!state.taskDetail?.summary || !state.taskDetail?.detail) {
        renderTaskDetailEmpty();
        return;
    }

    const summary = state.taskDetail.summary;
    const detail = state.taskDetail.detail;
    const detailSections = [
        {
            id: "detail-section-diagnostics",
            label: "模型诊断",
            title: "大模型与服务商诊断",
            content: buildLlmExecutionPanel(detail.llm_execution),
        },
        {
            id: "detail-section-quality",
            label: "质量面板",
            title: "质量面板",
            content: buildQualityPanel(detail.quality_panel),
        },
        {
            id: "detail-section-summary",
            label: "执行摘要",
            title: "执行摘要",
            content: `
                <div class="eda-summary">${buildEdaSummary(summary.eda_summary)}</div>
                <div class="repair-history">${buildRepairHistory(summary.repair_history)}</div>
            `,
        },
        {
            id: "detail-section-assets",
            label: "任务资产",
            title: "任务资产",
            content: buildDetailAssets(detail.assets, summary.status.task_id),
        },
        {
            id: "detail-section-waveforms",
            label: "波形缩略卡",
            title: "波形缩略卡",
            content: buildWaveformGrid(detail.waveform_assets),
        },
        {
            id: "detail-section-artifacts",
            label: "产物预览",
            title: "生成产物预览",
            content: buildPreviewGrid(detail.artifact_previews, "当前还没有可预览的生成产物。"),
        },
        {
            id: "detail-section-editor",
            label: "代码工作台",
            title: "交付文件工作台",
            content: buildArtifactWorkbench(detail.artifact_previews, summary.status.task_id),
        },
        {
            id: "detail-section-logs",
            label: "日志输出",
            title: "日志与修复输出",
            content: buildPreviewGrid(detail.log_previews, "当前还没有日志或 repair 输出。"),
        },
        {
            id: "detail-section-diffs",
            label: "差异视图",
            title: "原始文件差异视图",
            content: buildDiffGrid(detail.diff_previews),
        },
    ];
    cleanupDetailOutline();
    container.className = "detail-shell";
    container.innerHTML = `
        <div class="detail-head">
            <div>
                <p class="panel-kicker">${escapeHtml(summary.status.task_kind_title)}</p>
                <h3>${escapeHtml(summary.status.title)}</h3>
                <p class="detail-meta">${escapeHtml(formatMode(summary.status.mode))} | ${escapeHtml(formatOrigin(summary.status.origin))} | ${escapeHtml(summary.status.output_dir)}</p>
                <p class="detail-meta">状态：${escapeHtml(formatTaskStatus(summary.status))} | 阶段：${escapeHtml(summary.progress.stage_label)} | 进度：${escapeHtml(String(summary.progress.percent))}%</p>
                ${summary.status.cancel_requested_at ? `<p class="detail-meta">取消请求时间：${escapeHtml(formatDate(summary.status.cancel_requested_at))}${summary.status.cancellation_stage ? ` | 中断检查点：${escapeHtml(summary.status.cancellation_stage)}` : ""}</p>` : ""}
            </div>
            <div class="task-actions">
                <a class="secondary-button button-link" href="/api/tasks/${escapeHtml(summary.status.task_id)}/download">一键下载 ZIP</a>
                <a class="secondary-button button-link" href="${escapeHtml(buildVsCodeFolderUrl(summary.status.output_dir))}">在 VS Code 打开</a>
                ${summary.status.status === "succeeded" ? `<button class="secondary-button" type="button" data-task-action="save-template" data-task-id="${escapeHtml(summary.status.task_id)}">加入个人模板库</button>` : ""}
                ${buildTaskActionButtons(summary)}
            </div>
        </div>
        <nav class="detail-outline" aria-label="详情章节导航">
            ${detailSections
                .map(
                    (section) => `<a class="detail-outline__link" href="#${escapeHtml(section.id)}">${escapeHtml(section.label)}</a>`,
                )
                .join("")}
        </nav>
        <div class="detail-grid">
            ${detailSections
                .map(
                    (section) => `
                        <section id="${escapeHtml(section.id)}" class="detail-section">
                            <h3>${escapeHtml(section.title)}</h3>
                            ${section.content}
                        </section>
                    `,
                )
                .join("")}
        </div>
    `;
    setupDetailOutline(detailSections.map((section) => section.id));
    setupArtifactWorkbench(detail.artifact_previews, summary.status.task_id);
}

function buildVsCodeFolderUrl(outputDir) {
    const normalized = String(outputDir || "").replaceAll("\\", "/");
    return `vscode://file/${normalized}`;
}

function buildArtifactWorkbench(previews, taskId) {
    const editable = (previews || []).filter((preview) =>
        ["rtl/rtl_code.v", "tb/testbench.v", "doc/specification.md", "doc/delivery_report.md", "rtl_code.v", "testbench.v", "specification.md", "delivery_report.md"].includes(preview.relative_path || preview.file_name),
    );
    if (!editable.length) {
        return `<div class="empty-state">任务完成后，可在这里直接编辑 RTL、测试平台与文档。</div>`;
    }
    return `
        <div class="artifact-workbench" data-task-id="${escapeHtml(taskId)}">
            <aside class="artifact-file-tree" aria-label="交付文件目录">
                <div class="editor-tree-title">文件目录</div>
                ${editable.map((preview, index) => `
                    <button type="button" class="editor-file${index === 0 ? " is-active" : ""}" data-editor-file="${escapeHtml(preview.relative_path || preview.file_name)}">
                        <span>${escapeHtml((preview.relative_path || preview.file_name).split("/").slice(0, -1).join("/") || "legacy")}</span>
                        <strong>${escapeHtml((preview.relative_path || preview.file_name).split("/").at(-1))}</strong>
                    </button>
                `).join("")}
            </aside>
            <section class="artifact-editor-pane">
                <div class="artifact-editor-toolbar">
                    <code id="artifact-editor-path"></code>
                    <div>
                        <button type="button" class="secondary-button" id="artifact-editor-save">保存文件</button>
                        <button type="button" class="primary-button" id="artifact-editor-validate">重新验证 RTL/TB</button>
                    </div>
                </div>
                <textarea id="artifact-editor" spellcheck="false" aria-label="产物代码编辑器"></textarea>
                <div class="artifact-editor-status" id="artifact-editor-status">就绪</div>
            </section>
        </div>
    `;
}

function setupArtifactWorkbench(previews, taskId) {
    const root = document.querySelector(".artifact-workbench");
    if (!root) return;
    const previewMap = new Map((previews || []).map((preview) => [preview.relative_path || preview.file_name, preview]));
    const editor = root.querySelector("#artifact-editor");
    const pathLabel = root.querySelector("#artifact-editor-path");
    const status = root.querySelector("#artifact-editor-status");
    let activePreview = null;

    async function selectFile(fileName) {
        const preview = previewMap.get(fileName);
        if (!preview) return;
        activePreview = preview;
        root.querySelectorAll("[data-editor-file]").forEach((button) => {
            button.classList.toggle("is-active", button.dataset.editorFile === fileName);
        });
        pathLabel.textContent = fileName;
        status.textContent = "正在读取…";
        const response = await fetch(preview.raw_url);
        if (!response.ok) throw new Error(`读取文件失败：HTTP ${response.status}`);
        editor.value = await response.text();
        status.textContent = `${formatBytes(new Blob([editor.value]).size)} · 可编辑`;
    }

    root.querySelectorAll("[data-editor-file]").forEach((button) => {
        button.addEventListener("click", () => selectFile(button.dataset.editorFile).catch(reportError));
    });
    root.querySelector("#artifact-editor-save").addEventListener("click", async () => {
        if (!activePreview) return;
        status.textContent = "正在保存…";
        await fetchJson(activePreview.raw_url, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: editor.value }),
        });
        status.textContent = "已保存；请重新验证以刷新质量门。";
    });
    root.querySelector("#artifact-editor-validate").addEventListener("click", async () => {
        status.textContent = "正在运行仿真与综合…";
        await fetchJson(`/api/tasks/${taskId}/revalidate`, { method: "POST" });
        status.textContent = "验证完成，正在刷新结果…";
        await loadTaskDetail(taskId, { navigate: false, silent: true });
    });
    const first = root.querySelector("[data-editor-file]");
    if (first) selectFile(first.dataset.editorFile).catch(reportError);
}

function renderTaskDetailEmpty(text = "选择一个任务，查看截图、日志快照和生成产物预览。", options = {}) {
    const container = document.getElementById("task-detail");
    cleanupDetailOutline();
    container.className = "empty-state";
    container.textContent = text;
    if (options.authLocked) {
        container.dataset.authLocked = "true";
    } else {
        delete container.dataset.authLocked;
    }
}

function renderTaskDetailLoading() {
    const container = document.getElementById("task-detail");
    cleanupDetailOutline();
    container.className = "detail-loading";
    container.textContent = "正在加载任务详情...";
}

function renderTaskDetailError(error) {
    const container = document.getElementById("task-detail");
    cleanupDetailOutline();
    container.className = "empty-state";
    container.textContent = error?.message || "任务详情加载失败。";
}

function setupDetailOutline(sectionIds) {
    cleanupDetailOutline();

    const outline = document.querySelector("#task-detail .detail-outline");
    if (!outline) {
        return;
    }

    const sections = sectionIds
        .map((id) => document.getElementById(id))
        .filter(Boolean);
    if (!sections.length) {
        return;
    }

    const links = new Map(
        Array.from(outline.querySelectorAll(".detail-outline__link"), (link) => {
            const sectionId = (link.getAttribute("href") || "").replace(/^#/, "");
            return [sectionId, link];
        }),
    );

    const setActive = (activeId) => {
        links.forEach((link, sectionId) => {
            const isActive = sectionId === activeId;
            link.classList.toggle("is-active", isActive);
            if (isActive) {
                link.setAttribute("aria-current", "true");
            } else {
                link.removeAttribute("aria-current");
            }
        });
    };

    const computeActiveId = () => {
        const anchorOffset = Math.max(outline.getBoundingClientRect().height + 220, 280);
        let activeId = sections[0].id;
        for (const section of sections) {
            if (section.getBoundingClientRect().top <= anchorOffset) {
                activeId = section.id;
            }
        }
        return activeId;
    };

    let frameId = 0;
    const updateActive = () => {
        frameId = 0;
        setActive(computeActiveId());
    };
    const scheduleUpdate = () => {
        if (frameId) {
            return;
        }
        frameId = window.requestAnimationFrame(updateActive);
    };
    const handleOutlineClick = (event) => {
        const link = event.target.closest(".detail-outline__link");
        if (!link) {
            return;
        }
        setActive((link.getAttribute("href") || "").replace(/^#/, ""));
    };

    outline.addEventListener("click", handleOutlineClick);
    window.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
    updateActive();

    state.detailOutlineCleanup = () => {
        outline.removeEventListener("click", handleOutlineClick);
        window.removeEventListener("scroll", scheduleUpdate);
        window.removeEventListener("resize", scheduleUpdate);
        if (frameId) {
            window.cancelAnimationFrame(frameId);
        }
    };
}

function cleanupDetailOutline() {
    if (!state.detailOutlineCleanup) {
        return;
    }
    const cleanup = state.detailOutlineCleanup;
    state.detailOutlineCleanup = null;
    cleanup();
}

function buildLlmExecutionPanel(trace) {
    if (!trace) {
        return `<div class="empty-state">当前任务还没有记录大模型或服务商诊断信息。</div>`;
    }

    const capability = trace.capability_probe;
    return `
        <article class="preview-card diagnostic-card">
            <div class="preview-card-head">
                <div>
                    <p class="task-kind-label">模型传输协议</p>
                    <h4>${escapeHtml(formatTransport(trace.transport))}</h4>
                </div>
            </div>
            <div class="diagnostic-list">
                <p><strong>请求模式：</strong>${escapeHtml(formatTransport(trace.transport_requested))}</p>
                <p><strong>响应标识：</strong>${escapeHtml(trace.response_id || "无")}</p>
                <p><strong>最后阶段：</strong>${escapeHtml(trace.last_operation_label || trace.status || "无")}</p>
                <p><strong>服务商状态：</strong>${escapeHtml(trace.response_status || "无")}</p>
                <p><strong>服务商取消：</strong>${escapeHtml(trace.provider_cancel_requested ? (trace.provider_cancel_completed ? "已发出并确认" : "已请求") : "未触发")}</p>
                ${trace.last_error ? `<p><strong>最后错误：</strong>${escapeHtml(trace.last_error)}</p>` : ""}
                ${trace.updated_at ? `<p><strong>更新时间：</strong>${escapeHtml(formatDate(trace.updated_at))}</p>` : ""}
                ${capability ? `<p><strong>能力探测：</strong>${escapeHtml(formatCapabilityProbe(capability))}</p>` : ""}
                ${capability?.detail ? `<p><strong>探测说明：</strong>${escapeHtml(capability.detail)}</p>` : ""}
            </div>
        </article>
    `;
}

function buildQualityPanel(panel) {
    if (!panel) {
        return `<div class="empty-state">当前任务还没有质量面板数据。</div>`;
    }

    return `
        <div class="quality-panel-grid">
            ${buildSkillGovernanceCard(panel.skill_governance)}
            ${buildBenchmarkScoreCard(panel.benchmark)}
            ${buildFeedbackReportCard(panel.feedback_report)}
            ${buildFeedbackMemoryCard(panel.feedback_memory)}
        </div>
    `;
}

async function runPhase1Demo() {
    const button = document.getElementById("phase1-demo-button");
    try {
        if (!canAccessWorkspace()) {
            throw new Error("请先登录后再运行阶段一演示。");
        }
        button.disabled = true;
        button.textContent = "阶段一运行中…";
        const response = await fetchJson("/api/demo/phase1", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        setLiveIndicator("阶段一演示运行中", "live");
        switchScreen("workspace");
        await refreshAll();
        void monitorPhase1Demo(response.run_id);
    } catch (error) {
        if (String(error?.message || "").includes("正在运行")) {
            switchScreen("workspace");
            void monitorPhase1Demo();
        } else {
            button.disabled = false;
            button.textContent = "一键运行阶段一演示";
        }
        reportError(error);
    }
}

async function monitorPhase1Demo(expectedRunId = null) {
    const button = document.getElementById("phase1-demo-button");
    while (true) {
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
        try {
            const status = await fetchJson("/api/demo/phase1");
            if (expectedRunId && status.run_id && status.run_id !== expectedRunId) {
                break;
            }
            await refreshAll();
            if (status.status === "running") {
                continue;
            }
            button.disabled = false;
            button.textContent = "一键运行阶段一演示";
            if (status.status === "succeeded") {
                setLiveIndicator(`阶段一通过 ${status.passed_cases}/${status.case_count} · ${status.average_score} 分`, "live");
            } else if (status.status === "failed") {
                setLiveIndicator("阶段一演示失败", "error");
                reportError(new Error(status.error || "部分阶段一案例未通过，请打开任务详情查看日志。"));
            }
            break;
        } catch (error) {
            button.disabled = false;
            button.textContent = "一键运行阶段一演示";
            reportError(error);
            break;
        }
    }
}

async function runCompetitionBenchmark() {
    const button = document.getElementById("competition-benchmark-button");
    try {
        if (!canAccessWorkspace()) {
            throw new Error("请先登录后再运行模型盲测。");
        }
        button.disabled = true;
        button.textContent = "模型盲测运行中…";
        const response = await fetchJson("/api/benchmark/competition", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        setLiveIndicator(`模型盲测启动 · ${response.case_count || 0} 个未知任务`, "live");
        switchScreen("workspace");
        void monitorCompetitionBenchmark(response.run_id);
    } catch (error) {
        button.disabled = false;
        button.textContent = "运行模型盲测";
        reportError(error);
    }
}

async function monitorCompetitionBenchmark(expectedRunId = null) {
    const button = document.getElementById("competition-benchmark-button");
    while (true) {
        await new Promise((resolve) => window.setTimeout(resolve, 3000));
        try {
            const status = await fetchJson("/api/benchmark/competition");
            if (expectedRunId && status.run_id && status.run_id !== expectedRunId) {
                break;
            }
            await refreshAll();
            if (status.status === "running") {
                continue;
            }
            button.disabled = false;
            button.textContent = "运行模型盲测";
            if (["succeeded", "completed"].includes(status.status)) {
                setLiveIndicator(
                    `盲测 ${status.passed_cases}/${status.case_count} · Pass@1 ${status.pass_at_1_cases} · 修复后 ${status.pass_after_repair_cases}`,
                    status.status === "succeeded" ? "live" : "idle",
                );
            } else if (status.status === "failed") {
                setLiveIndicator("模型盲测失败", "error");
                reportError(new Error(status.error || "模型盲测执行失败。"));
            }
            break;
        } catch (error) {
            button.disabled = false;
            button.textContent = "运行模型盲测";
            reportError(error);
            break;
        }
    }
}

function buildSkillGovernanceCard(governance) {
    if (!governance?.available) {
        return `
            <article class="preview-card quality-card">
                <div class="preview-card-head"><div><p class="task-kind-label">可信技能</p><h4>未生成技能说明卡</h4></div></div>
                <div class="quality-stack"><p>当前任务还没有技能说明卡和安全报告。</p></div>
            </article>
        `;
    }

    const verdict = governance.security_verdict || "unknown";
    const alignmentLabels = { cataloged: "已编目", scanned: "已扫描", evaluated: "已评估", signed: "已签名", documented: "已文档化" };
    const alignment = Object.entries(governance.verified_skills_alignment || {});
    return `
        <article class="preview-card quality-card quality-card--benchmark">
            <div class="preview-card-head">
                <div>
                    <p class="task-kind-label">可信技能</p>
                    <h4>${escapeHtml(governance.name || "Digital IC Skill")}</h4>
                </div>
                <div class="quality-score-pill ${verdict === "pass" ? "is-pass" : "is-fail"}">${verdict === "pass" ? "本地扫描通过" : "本地扫描未通过"}</div>
            </div>
            <div class="quality-stack">
                <p><strong>版本：</strong>${escapeHtml(governance.version || "无")} | <strong>负责人：</strong>${escapeHtml(governance.owner || "无")}</p>
                <p><strong>包摘要：</strong>${escapeHtml((governance.package_digest || "无").slice(0, 16))}${governance.package_digest ? "…" : ""}</p>
                ${renderInlineChips("能力", governance.capabilities)}
                ${renderInlineChips("EDA 白名单", governance.allowed_eda_tools)}
                <p><strong>Verified Skills 治理证据：</strong>Catalog 编目、静态扫描、独立评测、数字签名与文档化五项状态统一展示。</p>
                <div class="quality-check-list">
                    ${alignment.map(([key, value]) => `
                        <div class="quality-check-row ${value.status === "pass" ? "is-pass" : "is-fail"}">
                            <div><strong>${escapeHtml(alignmentLabels[key] || key)}</strong><p>${escapeHtml(value.evidence || "无证据")}</p></div>
                            <span>${value.status === "pass" ? "已有证据" : value.status === "pending" ? "待完成" : "未通过"}</span>
                        </div>
                    `).join("")}
                </div>
                <div class="quality-check-list">
                    ${(governance.checks || [])
                        .map(
                            (check) => `
                                <div class="quality-check-row ${check.status === "pass" ? "is-pass" : "is-fail"}">
                                    <div>
                                        <strong>${escapeHtml(check.name)}</strong>
                                        <p>${escapeHtml(check.detail || "")}</p>
                                    </div>
                                    <span>${check.status === "pass" ? "通过" : "未通过"}</span>
                                </div>
                            `,
                        )
                        .join("")}
                </div>
            </div>
        </article>
    `;
}

function buildBenchmarkScoreCard(benchmark) {
    if (!benchmark?.available) {
        return `
            <article class="preview-card quality-card">
                <div class="preview-card-head"><div><p class="task-kind-label">盲测评估</p><h4>未关联盲测结果</h4></div></div>
                <div class="quality-stack"><p>当前任务目录下还没有盲测评分文件。</p></div>
            </article>
        `;
    }

    return `
        <article class="preview-card quality-card quality-card--benchmark">
            <div class="preview-card-head">
                <div>
                    <p class="task-kind-label">盲测评估</p>
                    <h4>${escapeHtml(benchmark.title || benchmark.case_id || "盲测案例")}</h4>
                </div>
                <div class="quality-score-pill ${benchmark.passed ? "is-pass" : "is-fail"}">${escapeHtml(String(benchmark.score ?? "无"))}</div>
            </div>
            <div class="quality-stack">
                <p><strong>案例：</strong>${escapeHtml(benchmark.case_id || "无")}</p>
                <p><strong>状态：</strong>${escapeHtml(benchmark.task_status || "无")}${benchmark.repair_attempts != null ? ` | 修复次数：${escapeHtml(String(benchmark.repair_attempts))}` : ""}</p>
                ${renderInlineChips("反馈标签", benchmark.feedback_tags)}
                ${renderInlineChips("语义指纹", benchmark.feedback_fingerprints)}
                <div class="quality-check-list">
                    ${(benchmark.checks || [])
                        .map(
                            (check) => `
                                <div class="quality-check-row ${check.passed ? "is-pass" : "is-fail"}">
                                    <div>
                                        <strong>${escapeHtml(check.name)}</strong>
                                        <p>${escapeHtml(check.detail || "")}</p>
                                    </div>
                                    <span>${escapeHtml(String(check.weight))}</span>
                                </div>
                            `,
                        )
                        .join("")}
                </div>
            </div>
        </article>
    `;
}

function buildFeedbackReportCard(report) {
    if (!report?.available) {
        return `
            <article class="preview-card quality-card">
                <div class="preview-card-head"><div><p class="task-kind-label">反馈闭环</p><h4>未生成反馈报告</h4></div></div>
                <div class="quality-stack"><p>当前任务目录下还没有反馈报告。</p></div>
            </article>
        `;
    }

    return `
        <article class="preview-card quality-card">
            <div class="preview-card-head">
                <div>
                    <p class="task-kind-label">反馈闭环</p>
                    <h4>${escapeHtml(formatOutcome(report.outcome))}</h4>
                </div>
            </div>
            <div class="quality-stack">
                ${renderInlineChips("错误标签", report.error_tags)}
                ${renderInlineChips("强化技能", report.skill_categories)}
                ${renderInlineChips("指纹键", report.fingerprint_keys)}
                <div class="quality-fingerprint-list">
                    ${(report.semantic_fingerprints || [])
                        .map(
                            (fingerprint) => `
                                <article class="quality-fingerprint-card">
                                    <p class="task-kind-label">${escapeHtml(fingerprint.skill_key || "技能")}</p>
                                    <h5>${escapeHtml(fingerprint.title || fingerprint.key)}</h5>
                                    <p>${escapeHtml(fingerprint.summary || "")}</p>
                                    <p class="quality-evidence">${escapeHtml(fingerprint.evidence || "")}</p>
                                </article>
                            `,
                        )
                        .join("")}
                </div>
                ${renderOrderedList("修复护栏", report.recommended_guardrails)}
            </div>
        </article>
    `;
}

function buildFeedbackMemoryCard(memory) {
    if (!memory?.available) {
        return `
            <article class="preview-card quality-card">
                <div class="preview-card-head"><div><p class="task-kind-label">经验记忆</p><h4>未聚合全局记忆</h4></div></div>
                <div class="quality-stack"><p>当前工程还没有聚合全局 FPGA 反馈记忆。</p></div>
            </article>
        `;
    }

    return `
        <article class="preview-card quality-card quality-card--memory">
            <div class="preview-card-head">
                <div>
                    <p class="task-kind-label">经验记忆</p>
                    <h4>全局失败记忆</h4>
                </div>
                <div class="quality-memory-meta">${escapeHtml(String(memory.entry_count || 0))} 条</div>
            </div>
            <div class="quality-stack">
                <p><strong>更新时间：</strong>${escapeHtml(memory.updated_at ? formatDate(memory.updated_at) : "无")}</p>
                ${renderCountGroup("高频错误标签", memory.top_tags)}
                ${renderCountGroup("高频技能缺口", memory.top_skill_categories)}
                ${renderCountGroup("高频语义指纹", memory.top_fingerprints)}
                ${renderOrderedList("近期护栏", memory.recent_guardrails)}
            </div>
        </article>
    `;
}

function renderInlineChips(label, values) {
    if (!values?.length) {
        return `<p><strong>${escapeHtml(label)}：</strong>无</p>`;
    }
    return `
        <div>
            <p><strong>${escapeHtml(label)}：</strong></p>
            <div class="quality-chip-row">
                ${values.map((value) => `<span class="quality-chip">${escapeHtml(String(value))}</span>`).join("")}
            </div>
        </div>
    `;
}

function renderCountGroup(title, items) {
    if (!items?.length) {
        return `<p><strong>${escapeHtml(title)}：</strong>无</p>`;
    }
    return `
        <div>
            <p><strong>${escapeHtml(title)}：</strong></p>
            <div class="quality-count-list">
                ${items
                    .map(
                        (item) => `
                            <div class="quality-count-row">
                                <span>${escapeHtml(item.label || item.key || "")}</span>
                                <strong>${escapeHtml(String(item.count ?? 0))}</strong>
                            </div>
                        `,
                    )
                    .join("")}
            </div>
        </div>
    `;
}

function renderOrderedList(title, items) {
    if (!items?.length) {
        return `<p><strong>${escapeHtml(title)}：</strong>无</p>`;
    }
    return `
        <div>
            <p><strong>${escapeHtml(title)}：</strong></p>
            <ol class="quality-ordered-list">
                ${items.map((item) => `<li>${escapeHtml(String(item))}</li>`).join("")}
            </ol>
        </div>
    `;
}

function buildDetailAssets(assets, taskId) {
    if (!assets?.length) {
        return `<div class="empty-state">还没有上传任务资产。</div>`;
    }

    return `
        <div class="detail-asset-grid">
            ${assets
                .map(
                    (asset) => `
                        <article class="detail-asset-card detail-asset-card--coverable">
                            ${isImageAsset(asset) ? `<img src="${escapeHtml(asset.url)}" alt="${escapeHtml(asset.caption || asset.file_name)}">` : ""}
                            <div>
                                <h4>${escapeHtml(asset.caption || asset.file_name)}</h4>
                                <p>${escapeHtml(asset.asset_type)}${asset.is_cover ? " · 当前封面" : ""}</p>
                            </div>
                            <div class="detail-asset-actions">
                                ${asset.is_cover
                                    ? `<span class="asset-cover-label">当前封面</span>`
                                    : `<button class="task-action-button" type="button" data-asset-action="cover" data-task-id="${escapeHtml(taskId)}" data-asset-id="${escapeHtml(asset.asset_id)}">设为封面</button>`}
                                <a class="preview-link" href="${escapeHtml(asset.url)}" target="_blank" rel="noreferrer">打开原文件</a>
                            </div>
                        </article>
                    `,
                )
                .join("")}
        </div>
    `;
}

function buildWaveformGrid(assets) {
    if (!assets?.length) {
        return `<div class="empty-state">当前还没有波形截图缩略卡。</div>`;
    }

    return `
        <div class="detail-asset-grid waveform-grid">
            ${assets
                .map(
                    (asset) => `
                        <article class="detail-asset-card waveform-card">
                            ${isImageAsset(asset) ? `<img src="${escapeHtml(asset.url)}" alt="${escapeHtml(asset.caption || asset.file_name)}">` : ""}
                            <div>
                                <h4>${escapeHtml(asset.caption || asset.file_name)}</h4>
                                <p>${escapeHtml(asset.file_name)}</p>
                            </div>
                            <a class="preview-link" href="${escapeHtml(asset.url)}" target="_blank" rel="noreferrer">打开波形原图</a>
                        </article>
                    `,
                )
                .join("")}
        </div>
    `;
}

function buildPreviewGrid(previews, emptyText) {
    if (!previews?.length) {
        return `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
    }

    return `
        <div class="preview-grid">
            ${previews
                .map(
                    (preview) => `
                        <article class="preview-card">
                            <div class="preview-card-head">
                                <div>
                                    <p class="task-kind-label">${escapeHtml(formatPreviewCategory(preview.category))}</p>
                                    <h4>${escapeHtml(preview.title)}</h4>
                                </div>
                                <a class="preview-link" href="${escapeHtml(preview.raw_url)}" target="_blank" rel="noreferrer">打开原文</a>
                            </div>
                            <p class="preview-meta">${escapeHtml(preview.file_name)} | ${escapeHtml(formatBytes(preview.size_bytes))} | ${escapeHtml(formatDate(preview.updated_at))}</p>
                            <pre class="preview-code">${escapeHtml(preview.preview_text)}</pre>
                        </article>
                    `,
                )
                .join("")}
        </div>
    `;
}

function buildDiffGrid(diffs) {
    if (!diffs?.length) {
        return `<div class="empty-state">当前还没有可展示的重试或原始文件差异。</div>`;
    }

    return `
        <div class="preview-grid diff-grid">
            ${diffs
                .map(
                    (diff) => `
                        <article class="preview-card diff-card">
                            <div class="preview-card-head">
                                <div>
                                    <p class="task-kind-label">${escapeHtml(formatPreviewCategory(diff.category))}差异</p>
                                    <h4>${escapeHtml(diff.title)}</h4>
                                </div>
                                <div class="preview-link-group">
                                    <a class="preview-link" href="${escapeHtml(diff.source_raw_url)}" target="_blank" rel="noreferrer">源文件</a>
                                    <a class="preview-link" href="${escapeHtml(diff.current_raw_url)}" target="_blank" rel="noreferrer">当前文件</a>
                                </div>
                            </div>
                            <p class="preview-meta">对比来源：${escapeHtml(diff.source_task_title)} · ${escapeHtml(diff.file_name)}</p>
                            <pre class="preview-code diff-code">${escapeHtml(diff.preview_text)}</pre>
                        </article>
                    `,
                )
                .join("")}
        </div>
    `;
}

function refreshSelectionState() {
    document.querySelectorAll(".task-card[data-task-id]").forEach((node) => {
        node.classList.toggle("is-selected", node.dataset.taskId === state.selectedTaskId);
    });

    document.querySelectorAll("[data-gallery-task-id]").forEach((node) => {
        node.classList.toggle("is-selected", node.dataset.galleryTaskId === state.selectedTaskId);
    });
}

function setReadyState(ready) {
    state.ready = ready;
    document.body.dataset.appReady = ready ? "true" : "false";
}

function setLiveIndicator(text, modifier) {
    const indicator = document.getElementById("live-indicator");
    indicator.textContent = text;
    indicator.className = `live-indicator live-indicator--${modifier}`;
}

function sortTasks(tasks) {
    return [...tasks].sort((left, right) => Date.parse(right.status.created_at) - Date.parse(left.status.created_at));
}

function getCoverAsset(assets) {
    return assets.find((asset) => asset.is_cover) || assets[0] || null;
}

function isImageAsset(asset) {
    return asset.content_type?.startsWith("image/") || /\.(svg|png|jpe?g|gif|webp)$/i.test(asset.file_name || "");
}

function formatBytes(value) {
    if (value < 1024) {
        return `${value} B`;
    }
    if (value < 1024 * 1024) {
        return `${(value / 1024).toFixed(1)} KB`;
    }
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString("zh-CN", { hour12: false });
}

function reportError(error, showAlert = true) {
    console.error(error);
    if (showAlert) {
        window.alert(error?.message || "请求失败");
    }
}

function buildMetadata() {
    const metadata = {};
    maybeAssign(metadata, "rtl_code", valueOf("rtl-code"));
    maybeAssign(metadata, "testbench_code", valueOf("testbench-code"));
    maybeAssign(metadata, "interface_contract", valueOf("interface-contract"));
    maybeAssign(metadata, "rtl_path", valueOf("rtl-path"));
    maybeAssign(metadata, "testbench_path", valueOf("tb-path"));
    maybeAssign(metadata, "contract_path", valueOf("contract-path"));
    return metadata;
}

function maybeAssign(payload, key, value) {
    if (value) {
        payload[key] = value;
    }
}

function valueOf(id) {
    return document.getElementById(id).value.trim();
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
        const errorText = await response.text();
        if (response.status === 401 && state.auth?.enabled) {
            state.auth = {
                enabled: true,
                authenticated: false,
                display_name: null,
                llm_config_saved: false,
                llm_config: null,
            };
            renderAuthPanel();
            teardownWorkspace("登录状态已失效，请重新登录。", { keepGallery: true });
        }
        throw new Error(parseApiErrorMessage(errorText, response.status));
    }
    return response.json();
}

function parseApiErrorMessage(errorText, status) {
    if (!errorText) {
        return `请求失败（HTTP ${status}）`;
    }
    try {
        const payload = JSON.parse(errorText);
        const details = Array.isArray(payload.detail) ? payload.detail : [payload.detail];
        const messages = details
            .map((detail) => (typeof detail === "string" ? detail : detail?.msg))
            .filter(Boolean);
        const message = messages.join("；");
        if (message.includes("requirement_text or task_file is required")) {
            return "请先粘贴赛题原文。接口契约、RTL 和测试平台会由智能体自动分析与生成。";
        }
        return message || `请求失败（HTTP ${status}）`;
    } catch {
        return errorText;
    }
}

function formatStatus(status) {
    return {
        pending: "等待中",
        running: "执行中",
        succeeded: "已完成",
        failed: "失败",
        canceled: "已取消",
    }[status] || status;
}

function formatTaskStatus(status) {
    if (status?.status === "running" && status.cancel_requested) {
        return "取消中";
    }
    return formatStatus(status?.status);
}

function formatBoolean(value) {
    if (value === true) {
        return "通过";
    }
    if (value === false) {
        return "未通过";
    }
    return "未执行";
}

function formatCapabilityProbe(capability) {
    const supportLabel = capability.supports_responses_background === true
        ? "支持后台响应接口"
        : capability.supports_responses_background === false
            ? "降级为对话补全接口"
            : "能力未知";
    return `${capability.source || "未知来源"} | ${supportLabel}`;
}

function formatExecutionStrategy(value) {
    return {
        workflow: "智能体闭环工作流",
        eda_triage: "EDA 故障分析",
        interface_contract_check: "接口契约校验",
    }[value] || value || "未指定策略";
}

function formatTransport(value) {
    return {
        auto: "自动选择",
        responses_background: "后台响应接口",
        chat: "对话补全接口",
    }[value] || value || "无（未调用大模型）";
}

function formatOrigin(value) {
    return {
        gui: "图形界面提交",
        api: "接口提交",
        queue: "任务队列",
        template_library: "参数化模板库",
        benchmark: "盲测评估",
    }[value] || value || "未知来源";
}

function formatMode(value) {
    return { fpga: "FPGA 原型模式" }[value] || value || "未指定模式";
}

function formatOutcome(value) {
    return {
        pass: "验证通过",
        failed: "验证失败",
        failure: "验证失败",
        succeeded: "验证通过",
    }[value] || value || "未知结果";
}

function formatPreviewCategory(value) {
    return { artifact: "产物", log: "日志" }[value] || value || "文件";
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
