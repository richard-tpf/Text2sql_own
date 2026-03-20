"""
表结构知识上传页面。

仅支持上传建表语句（DDL），支持两种方式：
- 手动输入 DDL 文本
- 上传 .md 文件，自动解析其中的建表语句
"""


def get_schema_upload_html() -> str:
    """生成表结构知识上传页面的完整 HTML。"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>表结构知识库 - 数仓开发助手</title>
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
                radial-gradient(circle at top left, rgba(21, 168, 168, 0.12), transparent 60%),
                radial-gradient(circle at bottom right, rgba(254, 93, 38, 0.08), transparent 65%);
        }
        body > * { position: relative; z-index: 1; }
        .toast { animation: slideDown 0.3s ease-out; }
        @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
        .history-item { animation: fadeIn 0.2s ease-out; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .tab-btn { transition: all 0.2s ease; }
        .tab-btn.active { border-bottom: 3px solid #15a8a8; color: #023d60; font-weight: 600; }
        .tab-btn:not(.active) { color: #94a3b8; }
        .drop-zone { transition: all 0.2s ease; }
        .drop-zone.dragover { border-color: #15a8a8; background: rgba(21, 168, 168, 0.06); }
    </style>
</head>
<body>
    <div class="max-w-4xl mx-auto p-5">
        <!-- 顶部导航 -->
        <div class="flex items-center justify-between mb-8">
            <div>
                <h1 class="text-3xl font-bold text-vanna-navy font-serif">🗄️ 表结构知识库</h1>
                <p class="text-slate-600 mt-1">上传建表语句（DDL）到表结构知识库</p>
            </div>
            <div class="flex gap-2">
                <a href="/knowledge/business"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-vanna-orange text-white text-sm font-medium rounded-lg hover:bg-vanna-magenta transition">
                    📖 业务文档库
                </a>
                <a href="/"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-vanna-navy text-white text-sm font-medium rounded-lg hover:bg-vanna-teal transition">
                    ← 返回对话
                </a>
            </div>
        </div>

        <!-- 主表单 -->
        <div class="bg-white rounded-xl shadow-lg border border-vanna-teal/30 overflow-hidden">
            <!-- Tab 切换：手动输入 / 文件上传 -->
            <div class="flex border-b border-gray-100">
                <button class="tab-btn active flex-1 py-4 text-center text-sm" id="tabManual" data-tab="manual">
                    ✏️ 手动输入 DDL
                </button>
                <button class="tab-btn flex-1 py-4 text-center text-sm" id="tabFile" data-tab="file">
                    📁 上传 MD 文件
                </button>
            </div>

            <!-- 手动输入面板 -->
            <div id="panelManual" class="p-6">
                <div class="mb-4">
                    <label class="block text-sm font-medium text-vanna-navy mb-1">库名.表名（可从 DDL 自动提取）</label>
                    <input id="titleInput" type="text"
                           placeholder="例如：zijie.dws_credit_daily_count_df"
                           class="w-full px-4 py-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-vanna-teal focus:border-transparent" />
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-vanna-navy mb-1">所属层级</label>
                    <select id="layerInput"
                            class="w-full px-4 py-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-vanna-teal bg-white">
                        <option value="">请选择层级...</option>
                        <option value="DWD">DWD</option>
                        <option value="MID">MID</option>
                        <option value="DWS">DWS</option>
                        <option value="ADS">ADS</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-vanna-navy mb-1">建表语句（DDL）</label>
                    <textarea id="contentInput" rows="14"
                              placeholder="请输入建表语句，例如：&#10;CREATE TABLE zijie.dws_credit_daily_count_df (&#10;  apply_date STRING COMMENT '申请日期',&#10;  apply_cnt BIGINT COMMENT '申请数'&#10;) COMMENT '授信日汇总表'&#10;PARTITIONED BY (ds STRING)&#10;STORED AS ORC;"
                              class="w-full px-4 py-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-vanna-teal focus:border-transparent font-mono leading-relaxed resize-y"
                    ></textarea>
                </div>
                <div class="mt-4 flex items-center justify-between">
                    <div id="resultToastManual" class="hidden"></div>
                    <div class="flex gap-3 ml-auto">
                        <button id="clearBtn" class="px-5 py-2.5 text-sm font-medium text-slate-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition">清空</button>
                        <button id="submitBtn" class="px-6 py-2.5 text-sm font-medium text-white bg-vanna-teal rounded-lg hover:bg-vanna-navy transition">上传到表结构知识库</button>
                    </div>
                </div>
            </div>

            <!-- 文件上传面板 -->
            <div id="panelFile" class="p-6 hidden">
                <div class="mb-4 p-4 bg-vanna-teal/5 border border-vanna-teal/20 rounded-lg text-sm text-vanna-navy leading-relaxed">
                    <p class="font-semibold mb-2">📌 MD 文件格式说明</p>
                    <p>每个表用二级标题 <code class="bg-gray-100 px-1 rounded">## 库名.表名</code> 开头，下面包含三部分：</p>
                    <ul class="mt-1 ml-4 list-disc text-xs text-slate-600 space-y-0.5">
                        <li><code class="bg-gray-100 px-1 rounded">### 所属层级</code> — DWD / MID / DWS / ADS</li>
                        <li><code class="bg-gray-100 px-1 rounded">### 建表语句</code> — 包含完整的 CREATE TABLE DDL（放在 ```sql 代码块中）</li>
                        <li><code class="bg-gray-100 px-1 rounded">### 来源表</code> — 该表的上游依赖表（每行一个，没有则留空）</li>
                    </ul>
                </div>

                <!-- 拖拽上传区域 -->
                <div id="dropZone" class="drop-zone border-2 border-dashed border-gray-300 rounded-xl p-10 text-center cursor-pointer hover:border-vanna-teal">
                    <div class="text-4xl mb-3">📄</div>
                    <p class="text-vanna-navy font-medium">拖拽 .md 文件到此处，或点击选择文件</p>
                    <p class="text-xs text-slate-400 mt-2">仅支持 .md 格式的 Markdown 文件</p>
                    <input id="fileInput" type="file" accept=".md" class="hidden" />
                </div>

                <!-- 文件预览 -->
                <div id="filePreview" class="hidden mt-4">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="text-vanna-teal">📎</span>
                            <span id="fileName" class="text-sm font-medium text-vanna-navy"></span>
                            <span id="fileTableCount" class="text-xs text-slate-500"></span>
                        </div>
                        <button id="removeFileBtn" class="text-xs text-red-500 hover:text-red-700">移除文件</button>
                    </div>
                    <div id="parsedPreview" class="max-h-64 overflow-y-auto border border-gray-200 rounded-lg p-4 bg-gray-50 text-sm font-mono"></div>
                </div>

                <div class="mt-4 flex items-center justify-between">
                    <div id="resultToastFile" class="hidden"></div>
                    <div class="flex gap-3 ml-auto">
                        <button id="uploadFileBtn" class="px-6 py-2.5 text-sm font-medium text-white bg-vanna-teal rounded-lg hover:bg-vanna-navy transition disabled:opacity-50 disabled:cursor-not-allowed" disabled>
                            批量上传到表结构知识库
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- 上传历史 -->
        <div class="mt-8 bg-white rounded-xl shadow-lg border border-vanna-teal/30 overflow-hidden">
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

        // ========== 手动输入相关 ==========
        const titleInput = document.getElementById('titleInput');
        const layerInput = document.getElementById('layerInput');
        const contentInput = document.getElementById('contentInput');
        const submitBtn = document.getElementById('submitBtn');
        const clearBtn = document.getElementById('clearBtn');
        const resultToastManual = document.getElementById('resultToastManual');
        let uploading = false;

        // ========== 文件上传相关 ==========
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const filePreview = document.getElementById('filePreview');
        const fileName = document.getElementById('fileName');
        const fileTableCount = document.getElementById('fileTableCount');
        const removeFileBtn = document.getElementById('removeFileBtn');
        const parsedPreview = document.getElementById('parsedPreview');
        const uploadFileBtn = document.getElementById('uploadFileBtn');
        const resultToastFile = document.getElementById('resultToastFile');
        let parsedTables = [];  // 解析后的表结构列表

        // ========== 历史记录 ==========
        const historyList = document.getElementById('historyList');
        const historyEmpty = document.getElementById('historyEmpty');
        const historyCount = document.getElementById('historyCount');
        const history = [];

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
            div.innerHTML = icon +
                '<div class="flex-1 min-w-0">' +
                    '<div class="flex items-center gap-2 mb-1">' +
                        '<span class="text-xs font-medium px-2 py-0.5 rounded-full bg-vanna-teal/10 text-vanna-teal">📋 建表语句</span>' +
                        '<span class="text-xs text-slate-400">' + item.time + '</span>' +
                        (item.source ? '<span class="text-xs text-slate-400">(' + item.source + ')</span>' : '') +
                    '</div>' +
                    '<div class="text-sm text-vanna-navy truncate">' + item.message + '</div>' +
                    '<div class="text-xs text-slate-400 mt-1 truncate font-mono">' + item.preview + '</div>' +
                '</div>';
            historyList.insertBefore(div, historyList.firstChild);
        }

        // ========== 手动输入提交 ==========
        submitBtn.addEventListener('click', async () => {
            const ddl = contentInput.value.trim();
            if (!ddl) { showToast(resultToastManual, '请输入建表语句', 'error'); return; }
            // 尝试从 DDL 中提取表名
            const tableNameInput = titleInput.value.trim();
            let tableName = tableNameInput;
            if (!tableName) {
                const match = ddl.match(/CREATE\\s+(?:EXTERNAL\\s+)?TABLE\\s+(?:IF\\s+NOT\\s+EXISTS\\s+)?([\\w.]+)/i);
                tableName = match ? match[1] : '';
            }
            if (!tableName) { showToast(resultToastManual, '请填写表名，或确保 DDL 中包含 CREATE TABLE 语句', 'error'); return; }
            if (uploading) return;
            uploading = true;
            submitBtn.disabled = true;
            submitBtn.textContent = '上传中...';
            hideToast(resultToastManual);
            try {
                const resp = await fetch('/api/knowledge/schema/upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ table_name: tableName, layer: layerInput.value, ddl: ddl, source_tables: '' })
                });
                if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.detail || '上传失败'); }
                const data = await resp.json();
                showToast(resultToastManual, data.message || '上传成功', 'success');
                addHistoryItem({ success: true, message: data.message, preview: tableName + ' | ' + ddl.substring(0, 80), time: new Date().toLocaleTimeString('zh-CN'), source: '手动输入' });
                titleInput.value = '';
                contentInput.value = '';
            } catch (e) {
                showToast(resultToastManual, e.message, 'error');
                addHistoryItem({ success: false, message: e.message, preview: ddl.substring(0, 120), time: new Date().toLocaleTimeString('zh-CN'), source: '手动输入' });
            } finally {
                uploading = false;
                submitBtn.disabled = false;
                submitBtn.textContent = '上传到表结构知识库';
            }
        });

        clearBtn.addEventListener('click', () => { titleInput.value = ''; layerInput.value = ''; contentInput.value = ''; hideToast(resultToastManual); });

        // ========== MD 文件解析 ==========
        // 按二级标题（## 库名.表名）拆分，解析四部分：表名、所属层级、建表语句、来源表
        function parseMdFile(text) {
            const lines = text.split('\\n');
            const tables = [];
            let currentTableName = '';
            let currentSection = '';  // 'layer' | 'ddl' | 'source' | ''
            let layerLines = [];
            let ddlLines = [];
            let sourceLines = [];
            let inCodeBlock = false;

            function saveCurrentTable() {
                if (currentTableName) {
                    const layer = layerLines.join('').trim();
                    const ddl = ddlLines.join('\\n').trim();
                    const sources = sourceLines
                        .map(l => l.replace(/^[-*]\\s*/, '').trim())
                        .filter(l => l.length > 0);
                    if (ddl) {
                        let content = '表名: ' + currentTableName + '\\n\\n建表语句:\\n' + ddl;
                        if (layer) {
                            content = '表名: ' + currentTableName + '\\n层级: ' + layer + '\\n\\n建表语句:\\n' + ddl;
                        }
                        if (sources.length > 0) {
                            content += '\\n\\n来源表:\\n' + sources.map(s => '- ' + s).join('\\n');
                        }
                        tables.push({ title: currentTableName, layer: layer, content: content, ddl: ddl, sources: sources });
                    }
                }
            }

            for (const line of lines) {
                const h2Match = line.match(/^##\\s+([^#].+)/);
                if (h2Match && !inCodeBlock) {
                    saveCurrentTable();
                    currentTableName = h2Match[1].trim();
                    currentSection = '';
                    layerLines = [];
                    ddlLines = [];
                    sourceLines = [];
                    continue;
                }

                if (!currentTableName) continue;

                const h3Match = line.match(/^###\\s+(.+)/);
                if (h3Match && !inCodeBlock) {
                    const sectionName = h3Match[1].trim();
                    if (sectionName.includes('层级')) currentSection = 'layer';
                    else if (sectionName.includes('建表')) currentSection = 'ddl';
                    else if (sectionName.includes('来源')) currentSection = 'source';
                    else currentSection = '';
                    continue;
                }

                if (line.trim().startsWith('```')) {
                    inCodeBlock = !inCodeBlock;
                    continue;
                }

                if (currentSection === 'layer') {
                    layerLines.push(line);
                } else if (currentSection === 'ddl') {
                    ddlLines.push(line);
                } else if (currentSection === 'source') {
                    sourceLines.push(line);
                }
            }
            saveCurrentTable();
            return tables;
        }

        function handleFile(file) {
            if (!file || !file.name.endsWith('.md')) {
                showToast(resultToastFile, '请选择 .md 格式的文件', 'error');
                return;
            }
            const reader = new FileReader();
            reader.onload = (e) => {
                const text = e.target.result;
                parsedTables = parseMdFile(text);
                if (parsedTables.length === 0) {
                    showToast(resultToastFile, '未在文件中找到有效的表结构（需要 ## 库名.表名 + ### 建表语句），请检查文件格式', 'error');
                    return;
                }
                // 显示预览
                fileName.textContent = file.name;
                fileTableCount.textContent = '解析出 ' + parsedTables.length + ' 个表结构';
                let previewHtml = '';
                parsedTables.forEach((t, i) => {
                    const ddlPreview = t.ddl.substring(0, 100).replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    const sourcesText = t.sources.length > 0 ? t.sources.join(', ') : '<span class="italic text-slate-400">无</span>';
                    const layerText = t.layer || '<span class="italic text-slate-400">未指定</span>';
                    previewHtml += '<div class="' + (i > 0 ? 'mt-3 pt-3 border-t border-gray-200' : '') + '">';
                    previewHtml += '<div class="font-semibold text-vanna-navy">' + (i + 1) + '. ' + t.title + ' <span class="text-xs font-normal px-1.5 py-0.5 rounded bg-vanna-teal/10 text-vanna-teal">' + layerText + '</span></div>';
                    previewHtml += '<div class="text-xs text-slate-500 mt-1">DDL: ' + ddlPreview + (t.ddl.length > 100 ? '...' : '') + '</div>';
                    previewHtml += '<div class="text-xs text-slate-500 mt-0.5">来源表: ' + sourcesText + '</div>';
                    previewHtml += '</div>';
                });
                parsedPreview.innerHTML = previewHtml;
                filePreview.classList.remove('hidden');
                uploadFileBtn.disabled = false;
                hideToast(resultToastFile);
            };
            reader.readAsText(file);
        }

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
            parsedTables = [];
            filePreview.classList.add('hidden');
            uploadFileBtn.disabled = true;
            fileInput.value = '';
            hideToast(resultToastFile);
        });

        // ========== 文件批量上传 ==========
        uploadFileBtn.addEventListener('click', async () => {
            if (parsedTables.length === 0 || uploading) return;
            uploading = true;
            uploadFileBtn.disabled = true;
            uploadFileBtn.textContent = '上传中 (0/' + parsedTables.length + ')...';
            hideToast(resultToastFile);

            let successCount = 0;
            let failCount = 0;
            for (let i = 0; i < parsedTables.length; i++) {
                const t = parsedTables[i];
                uploadFileBtn.textContent = '上传中 (' + (i + 1) + '/' + parsedTables.length + ')...';
                try {
                    const sourceTables = t.sources.join(',');
                    const resp = await fetch('/api/knowledge/schema/upload', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ table_name: t.title, layer: t.layer || '', ddl: t.ddl, source_tables: sourceTables })
                    });
                    if (!resp.ok) throw new Error('上传失败');
                    const data = await resp.json();
                    successCount++;
                    addHistoryItem({ success: true, message: data.message, preview: t.title + ' | ' + t.ddl.substring(0, 80), time: new Date().toLocaleTimeString('zh-CN'), source: '文件导入' });
                } catch (e) {
                    failCount++;
                    addHistoryItem({ success: false, message: '上传失败: ' + t.title, preview: t.ddl.substring(0, 120), time: new Date().toLocaleTimeString('zh-CN'), source: '文件导入' });
                }
            }

            const msg = '上传完成：成功 ' + successCount + ' 条' + (failCount > 0 ? '，失败 ' + failCount + ' 条' : '');
            showToast(resultToastFile, msg, failCount > 0 ? 'error' : 'success');
            uploading = false;
            uploadFileBtn.disabled = false;
            uploadFileBtn.textContent = '批量上传到表结构知识库';
        });
    })();
    </script>
</body>
</html>"""
