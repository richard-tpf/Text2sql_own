"""
知识上传页面 HTML 模板。

提供独立的知识上传界面，支持三种知识类型：
- ddl: 建表语句
- business: 业务定义
- table-connect: 表关联定义
"""


def get_knowledge_upload_html() -> str:
    """生成知识上传页面的完整 HTML。"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知识库管理 - Vanna Agents</title>
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

        body::after {
            content: '';
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            background-image:
                radial-gradient(circle at 2px 2px, rgba(2, 61, 96, 0.3) 1px, transparent 0),
                linear-gradient(rgba(2, 61, 96, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, rgba(2, 61, 96, 0.1) 1px, transparent 1px);
            background-size: 32px 32px, 100px 100px, 100px 100px;
        }

        body > * {
            position: relative;
            z-index: 1;
        }

        /* 知识类型卡片选中效果 */
        .type-card {
            transition: all 0.2s ease;
            cursor: pointer;
        }
        .type-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }
        .type-card.selected {
            border-color: #15a8a8;
            background: rgba(21, 168, 168, 0.06);
            box-shadow: 0 0 0 2px #15a8a8;
        }

        /* 提交按钮动画 */
        .submit-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* 结果提示动画 */
        .toast {
            animation: slideDown 0.3s ease-out;
        }
        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* 历史记录条目动画 */
        .history-item {
            animation: fadeIn 0.2s ease-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="max-w-4xl mx-auto p-5">
        <!-- 顶部导航 -->
        <div class="flex items-center justify-between mb-8">
            <div>
                <h1 class="text-3xl font-bold text-vanna-navy font-serif">📚 知识库管理</h1>
                <p class="text-slate-600 mt-1">上传建表语句、业务定义、表关联定义到知识库</p>
            </div>
            <a href="/"
               class="inline-flex items-center gap-2 px-4 py-2 bg-vanna-navy text-white text-sm font-medium rounded-lg hover:bg-vanna-teal transition">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
                </svg>
                返回对话
            </a>
        </div>

        <!-- 主表单区域 -->
        <div class="bg-white rounded-xl shadow-lg border border-vanna-teal/30 overflow-hidden">
            <!-- 步骤 1: 选择知识类型 -->
            <div class="p-6 border-b border-gray-100">
                <h2 class="text-lg font-semibold text-vanna-navy mb-4 font-serif">
                    <span class="inline-flex items-center justify-center w-7 h-7 bg-vanna-teal text-white text-sm rounded-full mr-2">1</span>
                    选择知识类型
                </h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4" id="typeSelector">
                    <div class="type-card selected rounded-xl border-2 border-gray-200 p-5 text-center" data-type="ddl">
                        <div class="text-3xl mb-2">📋</div>
                        <div class="font-semibold text-vanna-navy">建表语句 (DDL)</div>
                        <div class="text-xs text-slate-500 mt-1">CREATE TABLE 等 DDL 语句</div>
                    </div>
                    <div class="type-card rounded-xl border-2 border-gray-200 p-5 text-center" data-type="business">
                        <div class="text-3xl mb-2">📖</div>
                        <div class="font-semibold text-vanna-navy">业务定义</div>
                        <div class="text-xs text-slate-500 mt-1">业务规则、术语定义、流程说明</div>
                    </div>
                    <div class="type-card rounded-xl border-2 border-gray-200 p-5 text-center" data-type="table-connect">
                        <div class="text-3xl mb-2">🔗</div>
                        <div class="font-semibold text-vanna-navy">表关联定义</div>
                        <div class="text-xs text-slate-500 mt-1">表与表之间的关联关系</div>
                    </div>
                </div>
            </div>

            <!-- 步骤 2: 填写内容 -->
            <div class="p-6 border-b border-gray-100">
                <h2 class="text-lg font-semibold text-vanna-navy mb-4 font-serif">
                    <span class="inline-flex items-center justify-center w-7 h-7 bg-vanna-teal text-white text-sm rounded-full mr-2">2</span>
                    填写知识内容
                </h2>

                <div class="mb-4">
                    <label class="block text-sm font-medium text-vanna-navy mb-1">标题（可选）</label>
                    <input id="titleInput" type="text"
                           placeholder="简要描述该知识的主题，例如：t_order - 订单表"
                           class="w-full px-4 py-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-vanna-teal focus:border-transparent" />
                </div>

                <div>
                    <label class="block text-sm font-medium text-vanna-navy mb-1">知识内容</label>
                    <textarea id="contentInput" rows="12"
                              class="w-full px-4 py-3 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-vanna-teal focus:border-transparent font-mono leading-relaxed resize-y"
                    ></textarea>
                    <p class="text-xs text-slate-400 mt-1" id="placeholderHint">请输入建表语句，例如 CREATE TABLE ...</p>
                </div>
            </div>

            <!-- 步骤 3: 提交 -->
            <div class="p-6 flex items-center justify-between">
                <div id="resultToast" class="hidden"></div>
                <div class="flex gap-3 ml-auto">
                    <button id="clearBtn"
                            class="px-5 py-2.5 text-sm font-medium text-slate-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition">
                        清空
                    </button>
                    <button id="submitBtn"
                            class="submit-btn px-6 py-2.5 text-sm font-medium text-white bg-vanna-teal rounded-lg hover:bg-vanna-navy transition">
                        上传到知识库
                    </button>
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
                <div class="p-6 text-center text-slate-400 text-sm" id="historyEmpty">
                    暂无上传记录，上传知识后将在此显示
                </div>
            </div>
        </div>
    </div>

    <script>
    (function() {
        // ========== 状态 ==========
        let selectedType = 'ddl';
        let uploading = false;
        const history = [];

        // 各类型的占位提示
        const placeholders = {
            'ddl': '请输入建表语句，例如：\\nCREATE TABLE t_order (\\n  id BIGINT PRIMARY KEY,\\n  user_id BIGINT NOT NULL COMMENT \\'用户ID\\',\\n  amount DECIMAL(10,2) COMMENT \\'订单金额\\'\\n) COMMENT=\\'订单表\\';',
            'business': '请输入业务知识，例如：\\n订单状态说明：\\n- PENDING: 待支付\\n- PAID: 已支付\\n- SHIPPED: 已发货\\n- COMPLETED: 已完成',
            'table-connect': '请输入表关联定义，例如：\\nt_order.user_id 关联 t_user.id（多对一）\\nt_order.id 关联 t_order_item.order_id（一对多）'
        };

        const typeLabels = {
            'ddl': '📋 建表语句',
            'business': '📖 业务定义',
            'table-connect': '🔗 表关联定义'
        };

        // ========== DOM 元素 ==========
        const typeCards = document.querySelectorAll('.type-card');
        const titleInput = document.getElementById('titleInput');
        const contentInput = document.getElementById('contentInput');
        const placeholderHint = document.getElementById('placeholderHint');
        const submitBtn = document.getElementById('submitBtn');
        const clearBtn = document.getElementById('clearBtn');
        const resultToast = document.getElementById('resultToast');
        const historyList = document.getElementById('historyList');
        const historyEmpty = document.getElementById('historyEmpty');
        const historyCount = document.getElementById('historyCount');

        // ========== 类型选择 ==========
        function updatePlaceholder() {
            contentInput.placeholder = placeholders[selectedType];
            const hints = {
                'ddl': '请输入建表语句，例如 CREATE TABLE ...',
                'business': '请输入业务规则、术语定义等',
                'table-connect': '请输入表与表之间的关联关系'
            };
            placeholderHint.textContent = hints[selectedType];
        }

        typeCards.forEach(card => {
            card.addEventListener('click', () => {
                typeCards.forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                selectedType = card.dataset.type;
                updatePlaceholder();
                hideToast();
            });
        });

        // ========== 提示消息 ==========
        function showToast(message, type) {
            resultToast.className = 'toast text-sm font-medium px-4 py-2 rounded-lg';
            if (type === 'success') {
                resultToast.className += ' bg-emerald-50 text-emerald-700 border border-emerald-200';
            } else {
                resultToast.className += ' bg-red-50 text-red-700 border border-red-200';
            }
            resultToast.textContent = message;
            resultToast.classList.remove('hidden');
        }

        function hideToast() {
            resultToast.classList.add('hidden');
        }

        // ========== 上传历史 ==========
        function addHistoryItem(item) {
            history.unshift(item);
            historyEmpty.classList.add('hidden');
            historyCount.textContent = '共 ' + history.length + ' 条';

            const div = document.createElement('div');
            div.className = 'history-item p-4 flex items-start gap-3';
            const statusIcon = item.success
                ? '<span class="text-emerald-500">✅</span>'
                : '<span class="text-red-500">❌</span>';
            const titleText = item.title ? ' — ' + item.title : '';
            div.innerHTML = statusIcon +
                '<div class="flex-1 min-w-0">' +
                    '<div class="flex items-center gap-2 mb-1">' +
                        '<span class="text-xs font-medium px-2 py-0.5 rounded-full bg-vanna-teal/10 text-vanna-teal">' +
                            typeLabels[item.type] +
                        '</span>' +
                        '<span class="text-xs text-slate-400">' + item.time + '</span>' +
                    '</div>' +
                    '<div class="text-sm text-vanna-navy truncate">' +
                        (item.success ? item.message + titleText : item.message) +
                    '</div>' +
                    '<div class="text-xs text-slate-400 mt-1 truncate font-mono">' +
                        item.preview +
                    '</div>' +
                '</div>';

            historyList.insertBefore(div, historyList.firstChild);
        }

        // ========== 提交 ==========
        submitBtn.addEventListener('click', async () => {
            const content = contentInput.value.trim();
            if (!content) {
                showToast('请输入知识内容', 'error');
                return;
            }
            if (uploading) return;

            uploading = true;
            submitBtn.disabled = true;
            submitBtn.textContent = '上传中...';
            hideToast();

            try {
                const body = {
                    content: content,
                    knowledge_type: selectedType,
                    title: titleInput.value.trim()
                };

                const resp = await fetch('/api/knowledge/upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });

                if (!resp.ok) {
                    const errData = await resp.json().catch(() => ({}));
                    throw new Error(errData.detail || '上传失败 (' + resp.status + ')');
                }

                const data = await resp.json();
                showToast(data.message || '上传成功', 'success');

                addHistoryItem({
                    success: true,
                    type: selectedType,
                    title: titleInput.value.trim(),
                    message: data.message,
                    preview: content.substring(0, 120),
                    time: new Date().toLocaleTimeString('zh-CN')
                });

                // 清空内容区域
                titleInput.value = '';
                contentInput.value = '';

            } catch (e) {
                showToast(e.message || '网络错误，请重试', 'error');
                addHistoryItem({
                    success: false,
                    type: selectedType,
                    title: titleInput.value.trim(),
                    message: e.message,
                    preview: content.substring(0, 120),
                    time: new Date().toLocaleTimeString('zh-CN')
                });
            } finally {
                uploading = false;
                submitBtn.disabled = false;
                submitBtn.textContent = '上传到知识库';
            }
        });

        // ========== 清空 ==========
        clearBtn.addEventListener('click', () => {
            titleInput.value = '';
            contentInput.value = '';
            hideToast();
        });

        // 初始化占位提示
        updatePlaceholder();
    })();
    </script>
</body>
</html>"""
