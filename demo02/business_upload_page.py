"""
业务文档知识上传页面。

支持上传三种类型：
- business: 业务知识
- requirement: 需求文档
- standard: 开发规范

支持两种方式：
- 手动输入文本
- 上传 .md 文件，自动解析其中的知识条目
"""


def get_business_upload_html() -> str:
    """生成业务文档知识上传页面的完整 HTML。"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>业务文档知识库 - 数仓开发助手</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        'vanna-navy': '#023d60',
                        'vanna-cream': '#e7e1cf',
                        'vanna-teal': '#15a8a8',
                        'vanna-orange': '#fe5d26',
                        'vanna-magenta': '#bf1363',
                    },
                    fontFamily: {
                        'sans': ['Space Grotesk', 'ui-sans-serif', 'system-ui'],
                        'serif': ['Roboto Slab', 'ui-serif', 'Georgia'],
                        'mono': ['Space Mono', 'ui-monospace', 'monospace'],
                    }
                }
            }
        }
    </script>
    <style>
        body {
            background: linear-gradient(to bottom, #e7e1cf, #ffffff, #e7e1cf);
            min-height: 100vh;
            position: relative;
            overflow-x: hidden;
        }
        body::before {
            content: '';
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            background:
                radial-gradient(circle at top left, rgba(254, 93, 38, 0.12), transparent 60%),
                radial-gradient(circle at bottom right, rgba(191, 19, 99, 0.08), transparent 65%);
        }
        body > * { position: relative; z-index: 1; }
        .type-card { transition: all 0.2s ease; cursor: pointer; }
        .type-card:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.1); }
        .type-card.selected { border-color: #fe5d26; background: rgba(254, 93, 38, 0.06); box-shadow: 0 0 0 2px #fe5d26; }
        .toast { animation: slideDown 0.3s ease-out; }
        @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
        .history-item { animation: fadeIn 0.2s ease-out; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .tab-btn { transition: all 0.2s ease; }
        .tab-btn.active { border-bottom: 3px solid #fe5d26; color: #023d60; font-weight: 600; }
        .tab-btn:not(.active) { color: #94a3b8; }
        .drop-zone { transition: all 0.2s ease; }
        .drop-zone.dragover { border-color: #fe5d26; background: rgba(254, 93, 38, 0.06); }
    </style>
</head>
<body>
    <div class="max-w-4xl mx-auto p-5">
        <!-- 顶部导航 -->
        <div class="flex items-center justify-between mb-8">
            <div>
                <h1 class="text-3xl font-bold text-vanna-navy font-serif">📖 业务文档知识库</h1>
                <p class="text-slate-600 mt-1">上传业务知识、需求文档、开发规范</p>
            </div>
            <div class="flex gap-2">
                <a href="/knowledge/schema"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-vanna-teal text-white text-sm font-medium rounded-lg hover:bg-vanna-navy transition">
                    🗄️ 表结构库
                </a>
                <a href="/"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-vanna-navy text-white text-sm font-medium rounded-lg hover:bg-vanna-teal transition">
                    ← 返回对话
                </a>
            </div>
        </div>

        <!-- 主表单 -->
        <div class="bg-white rounded-xl shadow-lg border border-vanna-orange/30 overflow-hidden">
            <!-- Tab 切换：手动输入 / 文件上传 -->
            <div class="flex border-b border-gray-100">
                <button class="tab-btn active flex-1 py-4 text-center text-sm" id="tabManual" data-tab="manual">
                    ✏️ 手动输入
                </button>
                <button class="tab-btn flex-1 py-4 text-center text-sm" id="tabFile" data-tab="file">
                    📁 上传 MD 文件
                </button>
            </div>

            <!-- ==================== 手动输入面板 ==================== -->
            <div id="panelManual">
                <!-- 步骤1: 选择类型 -->
                <div class="p-6 border-b border-gray-100">
                    <h2 class="text-lg font-semibold text-vanna-navy mb-4 font-serif">
                        <span class="inline-flex items-center justify-center w-7 h-7 bg-vanna-orange text-white text-sm rounded-full mr-2">1</span>
                        选择知识类型
                    </h2>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4" id="typeSelector">
                        <div class="type-card selected rounded-xl border-2 border-gray-200 p-5 text-center" data-type="business">
                            <div class="text-3xl mb-2">📖</div>
                            <div class="font-semibold text-vanna-navy">业务知识</div>
                            <div class="text-xs text-slate-500 mt-1">业务规则、术语定义、指标口径</div>
                        </div>
                        <div class="type-card rounded-xl border-2 border-gray-200 p-5 text-center" data-type="requirement">
                            <div class="text-3xl mb-2">📄</div>
                            <div class="font-semibold text-vanna-navy">需求文档</div>
                            <div class="text-xs text-slate-500 mt-1">需求方案、指标定义文档</div>
                        </div>
                        <div class="type-card rounded-xl border-2 border-gray-200 p-5 text-center" data-type="standard">
                            <div class="text-3xl mb-2">📏</div>
                            <div class="font-semibold text-vanna-navy">开发规范</div>
                            <div class="text-xs text-slate-500 mt-1">SQL 编写规范、命名规范、检查清单</div>
                        </div>
                    </div>
                </div>

                <!-- 步骤2: 填写内容 -->
                <div class="p-6 border-b border-gray-100">
                    <h2 class="text-lg font-semibold text-vanna-navy mb-4 font-serif">
                        <span class="inline-flex items-center justify-center w-7 h-7 bg-vanna-orange text-white text-sm rounded-full mr-2">2</span>
                        填写知识内容
                    </h2>
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-vanna-navy mb-1">标题（可选）</label>
                        <input id="titleInput" type="text"
                               placeholder="例如：授信全流程漏斗 - 指标定义"
                               class="w-full px-4 py-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-vanna-orange focus:border-transparent" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-vanna-navy mb-1">知识内容</label>
                        <textarea id="contentInput" rows="14"
                                  class="w-full px-4 py-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-vanna-orange focus:border-transparent font-mono leading-relaxed resize-y"
                        ></textarea>
                        <p class="text-xs text-slate-400 mt-1" id="placeholderHint">请输入业务知识</p>
                    </div>
                </div>

                <!-- 步骤3: 提交 -->
                <div class="p-6 flex items-center justify-between">
                    <div id="resultToastManual" class="hidden"></div>
                    <div class="flex gap-3 ml-auto">
                        <button id="clearBtn" class="px-5 py-2.5 text-sm font-medium text-slate-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition">清空</button>
                        <button id="submitBtn" class="px-6 py-2.5 text-sm font-medium text-white bg-vanna-orange rounded-lg hover:bg-vanna-magenta transition">上传到业务文档知识库</button>
                    </div>
                </div>
            </div>

            <!-- ==================== 文件上传面板 ==================== -->
            <div id="panelFile" class="hidden">
                <!-- 步骤1: 选择知识类型 -->
                <div class="p-6 border-b border-gray-100">
                    <h2 class="text-lg font-semibold text-vanna-navy mb-4 font-serif">
                        <span class="inline-flex items-center justify-center w-7 h-7 bg-vanna-orange text-white text-sm rounded-full mr-2">1</span>
                        选择知识类型
                    </h2>
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4" id="fileTypeSelector">
                        <div class="type-card rounded-xl border-2 border-gray-200 p-5 text-center" data-type="business">
                            <div class="text-3xl mb-2">📖</div>
                            <div class="font-semibold text-vanna-navy">业务知识</div>
                            <div class="text-xs text-slate-500 mt-1">业务规则、术语定义、指标口径</div>
                        </div>
                        <div class="type-card selected rounded-xl border-2 border-gray-200 p-5 text-center" data-type="requirement">
                            <div class="text-3xl mb-2">📄</div>
                            <div class="font-semibold text-vanna-navy">需求文档</div>
                            <div class="text-xs text-slate-500 mt-1">需求方案、指标定义文档</div>
                        </div>
                        <div class="type-card rounded-xl border-2 border-gray-200 p-5 text-center" data-type="standard">
                            <div class="text-3xl mb-2">📏</div>
                            <div class="font-semibold text-vanna-navy">开发规范</div>
                            <div class="text-xs text-slate-500 mt-1">SQL 编写规范、命名规范、检查清单</div>
                        </div>
                    </div>
                </div>

                <!-- 步骤2: 上传文件 -->
                <div class="p-6 border-b border-gray-100">
                    <h2 class="text-lg font-semibold text-vanna-navy mb-4 font-serif">
                        <span class="inline-flex items-center justify-center w-7 h-7 bg-vanna-orange text-white text-sm rounded-full mr-2">2</span>
                        上传 MD 文件
                    </h2>

                    <div class="mb-4 p-4 bg-vanna-orange/5 border border-vanna-orange/20 rounded-lg text-sm text-vanna-navy leading-relaxed">
                        <p class="font-semibold mb-2">📌 MD 文件格式说明</p>
                        <p>系统支持两种解析模式：</p>
                        <ul class="mt-1 ml-4 list-disc text-xs text-slate-600 space-y-1">
                            <li><span class="font-medium text-vanna-navy">整篇导入</span>：将整个 MD 文件作为一条知识存入（适合单篇需求文档、规范文档）</li>
                            <li><span class="font-medium text-vanna-navy">按章节拆分</span>：按一级标题 <code class="bg-gray-100 px-1 rounded"># 标题</code> 拆分为多条知识分别存入（适合包含多个独立需求的文档）</li>
                        </ul>
                        <p class="mt-2 text-xs text-slate-500">提示：如果文件中只有一个一级标题或没有一级标题，系统会自动使用整篇导入模式。</p>
                    </div>

                    <!-- 解析模式选择 -->
                    <div class="mb-4 flex items-center gap-4">
                        <label class="text-sm font-medium text-vanna-navy">解析模式：</label>
                        <label class="inline-flex items-center gap-1.5 cursor-pointer">
                            <input type="radio" name="parseMode" value="whole" checked class="accent-vanna-orange" />
                            <span class="text-sm text-slate-700">整篇导入</span>
                        </label>
                        <label class="inline-flex items-center gap-1.5 cursor-pointer">
                            <input type="radio" name="parseMode" value="split" class="accent-vanna-orange" />
                            <span class="text-sm text-slate-700">按章节拆分</span>
                        </label>
                    </div>

                    <!-- 拖拽上传区域 -->
                    <div id="dropZone" class="drop-zone border-2 border-dashed border-gray-300 rounded-xl p-10 text-center cursor-pointer hover:border-vanna-orange">
                        <div class="text-4xl mb-3">📄</div>
                        <p class="text-vanna-navy font-medium">拖拽 .md 文件到此处，或点击选择文件</p>
                        <p class="text-xs text-slate-400 mt-2">仅支持 .md 格式的 Markdown 文件</p>
                        <input id="fileInput" type="file" accept=".md" class="hidden" />
                    </div>

                    <!-- 文件预览 -->
                    <div id="filePreview" class="hidden mt-4">
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center gap-2">
                                <span class="text-vanna-orange">📎</span>
                                <span id="fileName" class="text-sm font-medium text-vanna-navy"></span>
                                <span id="fileItemCount" class="text-xs text-slate-500"></span>
                            </div>
                            <button id="removeFileBtn" class="text-xs text-red-500 hover:text-red-700">移除文件</button>
                        </div>
                        <div id="parsedPreview" class="max-h-72 overflow-y-auto border border-gray-200 rounded-lg p-4 bg-gray-50 text-sm"></div>
                    </div>
                </div>

                <!-- 步骤3: 上传 -->
                <div class="p-6 flex items-center justify-between">
                    <div id="resultToastFile" class="hidden"></div>
                    <div class="flex gap-3 ml-auto">
                        <button id="uploadFileBtn" class="px-6 py-2.5 text-sm font-medium text-white bg-vanna-orange rounded-lg hover:bg-vanna-magenta transition disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                            批量上传到业务文档知识库
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- 上传历史 -->
        <div class="mt-8 bg-white rounded-xl shadow-lg border border-vanna-orange/30 overflow-hidden">
            <div class="p-6 border-b border-gray-100 flex items-center justify-between">
                <h2 class="text-lg font-semibold text-vanna-navy font-serif">📝 本次上传记录</h2>
                <span id="historyCount" class="text-sm text-slate-500">共 0 条</span>
            </div>
            <div id="historyList" class="divide-y divide-gray-50">
                <div class="p-6 text-center text-slate-400 text-sm" id="historyEmpty">暂无上传记录</div>
            </div>
        </div>
    </div>

    <script>
    (function() {
        // ========== Tab 切换 ==========
        const tabManual = document.getElementById('tabManual');
        const tabFile = document.getElementById('tabFile');
        const panelManual = document.getElementById('panelManual');
        const panelFile = document.getElementById('panelFile');

        function switchTab(tab) {
            if (tab === 'manual') {
                tabManual.classList.add('active');
                tabFile.classList.remove('active');
                panelManual.classList.remove('hidden');
                panelFile.classList.add('hidden');
            } else {
                tabFile.classList.add('active');
                tabManual.classList.remove('active');
                panelFile.classList.remove('hidden');
                panelManual.classList.add('hidden');
            }
        }
        tabManual.addEventListener('click', () => switchTab('manual'));
        tabFile.addEventListener('click', () => switchTab('file'));

        // ========== 通用变量 ==========
        let selectedType = 'business';
        let fileSelectedType = 'requirement';
        let uploading = false;
        const history = [];
        const typeLabels = { 'business': '📖 业务知识', 'requirement': '📄 需求文档', 'standard': '📏 开发规范' };

        const placeholders = {
            'business': '请输入业务知识，例如：\\n授信通过率 = 授信通过数 / 授信申请数\\n授信申请数：当日提交授信申请的去重用户数\\n授信通过数：当日授信审批结果为"通过"的去重用户数',
            'requirement': '请输入需求文档内容，例如：\\n【授信全流程漏斗分析】\\n| 指标名称 | 字段性质 | 统计方式 | 取值来源 | 取值规则 | 展示格式 | 备注 |\\n| 日期 | 维度 | — | 来源表：order_info；字段：create_date | 取订单创建日期 | YYYY-MM-DD | |\\n| 申请数 | 原子指标 | 计数（去重） | 来源表：credit_apply；字段：user_id | 当日去重用户数 | 整数 | |',
            'standard': '请输入开发规范，例如：\\n所有表名必须带 zijie. schema 前缀\\nLEFT JOIN 后 SUM 聚合必须用 COALESCE(flag, 0) 包裹\\n分区条件 ds = \\'${bizdate}\\' 在每个 CTE 中都要加'
        };

        // ========== 手动输入相关 ==========
        const typeCards = document.querySelectorAll('#typeSelector .type-card');
        const titleInput = document.getElementById('titleInput');
        const contentInput = document.getElementById('contentInput');
        const placeholderHint = document.getElementById('placeholderHint');
        const submitBtn = document.getElementById('submitBtn');
        const clearBtn = document.getElementById('clearBtn');
        const resultToastManual = document.getElementById('resultToastManual');

        // ========== 文件上传相关 ==========
        const fileTypeCards = document.querySelectorAll('#fileTypeSelector .type-card');
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const filePreview = document.getElementById('filePreview');
        const fileNameEl = document.getElementById('fileName');
        const fileItemCount = document.getElementById('fileItemCount');
        const removeFileBtn = document.getElementById('removeFileBtn');
        const parsedPreview = document.getElementById('parsedPreview');
        const uploadFileBtn = document.getElementById('uploadFileBtn');
        const resultToastFile = document.getElementById('resultToastFile');
        let parsedItems = [];  // 解析后的知识条目列表
        let rawFileText = '';  // 原始文件内容

        // ========== 历史记录 ==========
        const historyList = document.getElementById('historyList');
        const historyEmpty = document.getElementById('historyEmpty');
        const historyCount = document.getElementById('historyCount');

        // ========== 通用函数 ==========
        function showToast(el, message, type) {
            el.className = 'toast text-sm font-medium px-4 py-2 rounded-lg';
            el.className += type === 'success'
                ? ' bg-emerald-50 text-emerald-700 border border-emerald-200'
                : ' bg-red-50 text-red-700 border border-red-200';
            el.textContent = message;
            el.classList.remove('hidden');
        }
        function hideToast(el) { el.classList.add('hidden'); }

        function addHistoryItem(item) {
            history.unshift(item);
            historyEmpty.classList.add('hidden');
            historyCount.textContent = '共 ' + history.length + ' 条';
            const div = document.createElement('div');
            div.className = 'history-item p-4 flex items-start gap-3';
            const icon = item.success ? '<span class="text-emerald-500">✅</span>' : '<span class="text-red-500">❌</span>';
            const titleText = item.title ? ' — ' + item.title : '';
            div.innerHTML = icon +
                '<div class="flex-1 min-w-0">' +
                    '<div class="flex items-center gap-2 mb-1">' +
                        '<span class="text-xs font-medium px-2 py-0.5 rounded-full bg-vanna-orange/10 text-vanna-orange">' + typeLabels[item.type] + '</span>' +
                        '<span class="text-xs text-slate-400">' + item.time + '</span>' +
                        (item.source ? '<span class="text-xs text-slate-400">(' + item.source + ')</span>' : '') +
                    '</div>' +
                    '<div class="text-sm text-vanna-navy truncate">' + (item.success ? item.message + titleText : item.message) + '</div>' +
                    '<div class="text-xs text-slate-400 mt-1 truncate font-mono">' + item.preview + '</div>' +
                '</div>';
            historyList.insertBefore(div, historyList.firstChild);
        }

        function escapeHtml(text) {
            return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        // ========== 手动输入：类型选择 ==========
        function updatePlaceholder() {
            contentInput.placeholder = placeholders[selectedType];
            const hints = { 'business': '请输入业务规则、指标口径等', 'requirement': '请输入需求方案文档内容', 'standard': '请输入开发规范内容' };
            placeholderHint.textContent = hints[selectedType];
        }

        typeCards.forEach(card => {
            card.addEventListener('click', () => {
                typeCards.forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                selectedType = card.dataset.type;
                updatePlaceholder();
                hideToast(resultToastManual);
            });
        });
        updatePlaceholder();

        // ========== 文件上传：类型选择 ==========
        fileTypeCards.forEach(card => {
            card.addEventListener('click', () => {
                fileTypeCards.forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                fileSelectedType = card.dataset.type;
                // 如果已有文件，重新解析预览
                if (rawFileText) {
                    reparseAndPreview();
                }
            });
        });

        // ========== 手动输入提交 ==========
        submitBtn.addEventListener('click', async () => {
            const content = contentInput.value.trim();
            if (!content) { showToast(resultToastManual, '请输入知识内容', 'error'); return; }
            if (uploading) return;
            uploading = true;
            submitBtn.disabled = true;
            submitBtn.textContent = '上传中...';
            hideToast(resultToastManual);
            try {
                const resp = await fetch('/api/knowledge/business/upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content, knowledge_type: selectedType, title: titleInput.value.trim() })
                });
                if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.detail || '上传失败'); }
                const data = await resp.json();
                showToast(resultToastManual, data.message || '上传成功', 'success');
                addHistoryItem({ success: true, type: selectedType, title: titleInput.value.trim(), message: data.message, preview: content.substring(0, 120), time: new Date().toLocaleTimeString('zh-CN'), source: '手动输入' });
                titleInput.value = '';
                contentInput.value = '';
            } catch (e) {
                showToast(resultToastManual, e.message, 'error');
                addHistoryItem({ success: false, type: selectedType, title: '', message: e.message, preview: content.substring(0, 120), time: new Date().toLocaleTimeString('zh-CN'), source: '手动输入' });
            } finally {
                uploading = false;
                submitBtn.disabled = false;
                submitBtn.textContent = '上传到业务文档知识库';
            }
        });

        clearBtn.addEventListener('click', () => { titleInput.value = ''; contentInput.value = ''; hideToast(resultToastManual); });

        // ========== MD 文件解析 ==========
        function getParseMode() {
            const radios = document.querySelectorAll('input[name="parseMode"]');
            for (const r of radios) { if (r.checked) return r.value; }
            return 'whole';
        }

        /**
         * 整篇导入模式：将整个文件作为一条知识。
         * 标题取第一个一级标题，如果没有则用文件名。
         */
        function parseWhole(text, fallbackTitle) {
            const content = text.trim();
            if (!content) return [];
            // 尝试提取第一个一级标题作为标题
            let title = fallbackTitle || '';
            const h1Match = content.match(/^#\\s+(.+)/m);
            if (h1Match) {
                title = h1Match[1].trim();
            }
            return [{ title: title, content: content }];
        }

        /**
         * 按章节拆分模式：按一级标题（# 标题）拆分为多条知识。
         * 每个一级标题下的所有内容（包括二级、三级标题）作为一条知识。
         */
        function parseSplit(text) {
            const lines = text.split('\\n');
            const items = [];
            let currentTitle = '';
            let currentLines = [];
            let hasH1 = false;

            // 收集一级标题之前的前言内容
            let preambleLines = [];
            let inPreamble = true;

            for (const line of lines) {
                const h1Match = line.match(/^#\\s+([^#].+)/);
                if (h1Match) {
                    hasH1 = true;
                    if (inPreamble) {
                        inPreamble = false;
                        // 前言内容如果有实质内容，也作为一条
                        const preamble = preambleLines.join('\\n').trim();
                        if (preamble && preamble.length > 10) {
                            items.push({ title: '文档前言', content: preamble });
                        }
                    }
                    // 保存上一个章节
                    if (currentTitle) {
                        const content = currentLines.join('\\n').trim();
                        if (content) {
                            items.push({ title: currentTitle, content: '# ' + currentTitle + '\\n' + content });
                        }
                    }
                    currentTitle = h1Match[1].trim();
                    currentLines = [];
                    continue;
                }

                if (inPreamble) {
                    preambleLines.push(line);
                } else {
                    currentLines.push(line);
                }
            }

            // 保存最后一个章节
            if (currentTitle) {
                const content = currentLines.join('\\n').trim();
                if (content) {
                    items.push({ title: currentTitle, content: '# ' + currentTitle + '\\n' + content });
                }
            }

            // 如果没有一级标题，整篇作为一条
            if (!hasH1) {
                const content = text.trim();
                if (content) {
                    items.push({ title: '（未分章节）', content: content });
                }
            }

            return items;
        }

        function reparseAndPreview() {
            const mode = getParseMode();
            if (mode === 'whole') {
                parsedItems = parseWhole(rawFileText, currentFileName);
            } else {
                parsedItems = parseSplit(rawFileText);
            }
            renderPreview();
        }

        let currentFileName = '';

        function renderPreview() {
            if (parsedItems.length === 0) {
                showToast(resultToastFile, '未在文件中找到有效内容，请检查文件', 'error');
                filePreview.classList.add('hidden');
                uploadFileBtn.disabled = true;
                return;
            }
            fileItemCount.textContent = '解析出 ' + parsedItems.length + ' 条知识';
            let previewHtml = '';
            parsedItems.forEach((item, i) => {
                const contentPreview = escapeHtml(item.content.substring(0, 200));
                previewHtml += '<div class="' + (i > 0 ? 'mt-3 pt-3 border-t border-gray-200' : '') + '">';
                previewHtml += '<div class="font-semibold text-vanna-navy">' + (i + 1) + '. ' + escapeHtml(item.title) + '</div>';
                previewHtml += '<div class="text-xs text-slate-500 mt-1 whitespace-pre-line">' + contentPreview + (item.content.length > 200 ? '...' : '') + '</div>';
                previewHtml += '<div class="text-xs text-slate-400 mt-0.5">字数：' + item.content.length + '</div>';
                previewHtml += '</div>';
            });
            parsedPreview.innerHTML = previewHtml;
            filePreview.classList.remove('hidden');
            uploadFileBtn.disabled = false;
            hideToast(resultToastFile);
        }

        function handleFile(file) {
            if (!file || !file.name.endsWith('.md')) {
                showToast(resultToastFile, '请选择 .md 格式的文件', 'error');
                return;
            }
            currentFileName = file.name.replace(/\\.md$/, '');
            const reader = new FileReader();
            reader.onload = (e) => {
                rawFileText = e.target.result;
                fileNameEl.textContent = file.name;
                reparseAndPreview();
            };
            reader.readAsText(file);
        }

        // 解析模式切换时重新解析
        document.querySelectorAll('input[name="parseMode"]').forEach(radio => {
            radio.addEventListener('change', () => {
                if (rawFileText) reparseAndPreview();
            });
        });

        // 拖拽事件
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
        });
        fileInput.addEventListener('change', () => { if (fileInput.files.length > 0) handleFile(fileInput.files[0]); });

        // 移除文件
        removeFileBtn.addEventListener('click', () => {
            parsedItems = [];
            rawFileText = '';
            currentFileName = '';
            filePreview.classList.add('hidden');
            uploadFileBtn.disabled = true;
            fileInput.value = '';
            hideToast(resultToastFile);
        });

        // ========== 文件批量上传 ==========
        uploadFileBtn.addEventListener('click', async () => {
            if (parsedItems.length === 0 || uploading) return;
            uploading = true;
            uploadFileBtn.disabled = true;
            uploadFileBtn.textContent = '上传中 (0/' + parsedItems.length + ')...';
            hideToast(resultToastFile);

            let successCount = 0;
            let failCount = 0;
            for (let i = 0; i < parsedItems.length; i++) {
                const item = parsedItems[i];
                uploadFileBtn.textContent = '上传中 (' + (i + 1) + '/' + parsedItems.length + ')...';
                try {
                    const resp = await fetch('/api/knowledge/business/upload', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            content: item.content,
                            knowledge_type: fileSelectedType,
                            title: item.title
                        })
                    });
                    if (!resp.ok) throw new Error('上传失败');
                    const data = await resp.json();
                    successCount++;
                    addHistoryItem({
                        success: true, type: fileSelectedType, title: item.title,
                        message: data.message, preview: item.content.substring(0, 120),
                        time: new Date().toLocaleTimeString('zh-CN'), source: '文件导入'
                    });
                } catch (e) {
                    failCount++;
                    addHistoryItem({
                        success: false, type: fileSelectedType, title: item.title,
                        message: '上传失败: ' + item.title,
                        preview: item.content.substring(0, 120),
                        time: new Date().toLocaleTimeString('zh-CN'), source: '文件导入'
                    });
                }
            }

            const msg = '上传完成：成功 ' + successCount + ' 条' + (failCount > 0 ? '，失败 ' + failCount + ' 条' : '');
            showToast(resultToastFile, msg, failCount > 0 ? 'error' : 'success');
            uploading = false;
            uploadFileBtn.disabled = false;
            uploadFileBtn.textContent = '批量上传到业务文档知识库';
        });
    })();
    </script>
</body>
</html>"""
