"""
自定义主页模板。

在原版 Vanna Agents 主页基础上，在登录后的界面中添加"知识管理"按钮，
点击后跳转到 /knowledge 页面进行知识上传。
"""

from vanna.servers.base.templates import get_vanna_component_script


def get_custom_index_html(
    dev_mode: bool = False,
    cdn_url: str = "https://img.vanna.ai/vanna-components.js",
    api_base_url: str = "",
) -> str:
    """生成带有知识管理按钮的自定义主页 HTML。"""
    component_script = get_vanna_component_script(dev_mode=dev_mode, cdn_url=cdn_url)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vanna Agents Chat</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        'vanna-navy': '#023d60',
                        'vanna-cream': '#e7e1cf',
                        'vanna-teal': '#15a8a8',
                        'vanna-orange': '#fe5d26',
                        'vanna-magenta': '#bf1363',
                    }},
                    fontFamily: {{
                        'sans': ['Space Grotesk', 'ui-sans-serif', 'system-ui'],
                        'serif': ['Roboto Slab', 'ui-serif', 'Georgia'],
                        'mono': ['Space Mono', 'ui-monospace', 'monospace'],
                    }}
                }}
            }}
        }}
    </script>
    <style>
        body {{
            background: linear-gradient(to bottom, #e7e1cf, #ffffff, #e7e1cf);
            min-height: 100vh;
            position: relative;
            overflow-x: hidden;
        }}
        body::before {{
            content: '';
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            background:
                radial-gradient(circle at top left, rgba(21, 168, 168, 0.12), transparent 60%),
                radial-gradient(circle at bottom right, rgba(254, 93, 38, 0.08), transparent 65%);
        }}
        body::after {{
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
        }}
        body > * {{
            position: relative;
            z-index: 1;
        }}
        vanna-chat {{
            width: 100%;
            height: 100%;
            display: block;
        }}
    </style>
    {component_script}
</head>
<body>
    <div class="max-w-6xl mx-auto p-5">
        <!-- 顶部标题 -->
        <div class="text-center mb-8">
            <h1 class="text-4xl font-bold text-vanna-navy mb-2 font-serif">Vanna Agents</h1>
            <p class="text-lg font-mono font-bold text-vanna-teal mb-4">DATA-FIRST AGENTS</p>
            <p class="text-slate-600 mb-4">基于知识库的智能问答助手</p>
            <div class="flex items-center justify-center gap-3">
                <a href="/knowledge"
                   class="inline-flex items-center gap-2 px-5 py-2.5 bg-vanna-orange text-white text-sm font-medium rounded-lg hover:bg-vanna-magenta transition shadow-md">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                    </svg>
                    知识管理
                </a>
                <a href="javascript:window.location='view-source:'+window.location.href"
                   class="inline-flex items-center gap-2 px-4 py-2 bg-vanna-teal text-white text-sm font-medium rounded-lg hover:bg-vanna-navy transition">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
                    </svg>
                    查看源码
                </a>
            </div>
        </div>

        <!-- 登录表单 -->
        <div id="loginContainer" class="max-w-md mx-auto mb-10 bg-white p-8 rounded-xl shadow-lg border border-vanna-teal/30">
            <div class="text-center mb-6">
                <h2 class="text-2xl font-semibold text-vanna-navy mb-2 font-serif">登录</h2>
                <p class="text-sm text-slate-600">选择邮箱以访问对话</p>
            </div>
            <div class="mb-5">
                <label for="emailInput" class="block mb-2 text-sm font-medium text-vanna-navy">邮箱地址</label>
                <select id="emailInput"
                        class="w-full px-4 py-3 text-sm border border-vanna-teal/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-vanna-teal focus:border-transparent bg-white">
                    <option value="">选择邮箱...</option>
                    <option value="admin@example.com">admin@example.com</option>
                    <option value="user@example.com">user@example.com</option>
                </select>
            </div>
            <button id="loginButton"
                    class="w-full px-4 py-3 bg-vanna-teal text-white text-sm font-medium rounded-lg hover:bg-vanna-navy focus:outline-none focus:ring-2 focus:ring-vanna-teal focus:ring-offset-2 transition disabled:bg-gray-400 disabled:cursor-not-allowed">
                继续
            </button>
            <div class="mt-5 p-3 bg-vanna-teal/10 border-l-4 border-vanna-teal rounded text-xs text-vanna-navy leading-relaxed">
                <strong>演示模式：</strong>邮箱将存储为 Cookie，随所有 API 请求自动发送。
            </div>
        </div>

        <!-- 已登录状态 -->
        <div id="loggedInStatus" class="hidden text-center p-4 bg-vanna-teal/10 border border-vanna-teal/30 rounded-lg mb-5">
            已登录：<span id="loggedInEmail" class="font-semibold text-vanna-navy"></span>
            <br>
            <button id="logoutButton" class="mt-2 px-3 py-1.5 bg-vanna-navy text-white text-xs rounded hover:bg-vanna-teal transition">
                退出登录
            </button>
        </div>

        <!-- 对话区域 -->
        <div id="chatSections" class="hidden">
            <div class="bg-white rounded-xl shadow-lg h-[600px] overflow-hidden border border-vanna-teal/30">
                <vanna-chat
                    api-base="{api_base_url}"
                    sse-endpoint="{api_base_url}/api/vanna/v2/chat_sse"
                    ws-endpoint="{api_base_url}/api/vanna/v2/chat_websocket"
                    poll-endpoint="{api_base_url}/api/vanna/v2/chat_poll">
                </vanna-chat>
            </div>

            <div class="mt-8 p-5 bg-white rounded-lg shadow border border-vanna-teal/30">
                <h3 class="text-lg font-semibold text-vanna-navy mb-3 font-serif">API 端点</h3>
                <ul class="space-y-2">
                    <li class="p-2 bg-vanna-cream/50 rounded font-mono text-sm">
                        <span class="font-bold text-vanna-teal mr-2">POST</span>{api_base_url}/api/vanna/v2/chat_sse - SSE 流式对话
                    </li>
                    <li class="p-2 bg-vanna-cream/50 rounded font-mono text-sm">
                        <span class="font-bold text-vanna-teal mr-2">WS</span>{api_base_url}/api/vanna/v2/chat_websocket - WebSocket 实时对话
                    </li>
                    <li class="p-2 bg-vanna-cream/50 rounded font-mono text-sm">
                        <span class="font-bold text-vanna-orange mr-2">POST</span>{api_base_url}/api/knowledge/upload - 上传知识
                    </li>
                    <li class="p-2 bg-vanna-cream/50 rounded font-mono text-sm">
                        <span class="font-bold text-vanna-orange mr-2">GET</span>/knowledge - 知识管理页面
                    </li>
                    <li class="p-2 bg-vanna-cream/50 rounded font-mono text-sm">
                        <span class="font-bold text-vanna-teal mr-2">GET</span>{api_base_url}/health - 健康检查
                    </li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        const getCookie = (name) => {{
            const value = `; ${{document.cookie}}`;
            const parts = value.split(`; ${{name}}=`);
            return parts.length === 2 ? parts.pop().split(';').shift() : null;
        }};
        const setCookie = (name, value) => {{
            const expires = new Date(Date.now() + 365 * 864e5).toUTCString();
            document.cookie = `${{name}}=${{value}}; expires=${{expires}}; path=/; SameSite=Lax`;
        }};
        const deleteCookie = (name) => {{
            document.cookie = `${{name}}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
        }};

        document.addEventListener('DOMContentLoaded', () => {{
            const email = getCookie('vanna_email');
            if (email) {{
                loginContainer.classList.add('hidden');
                loggedInStatus.classList.remove('hidden');
                chatSections.classList.remove('hidden');
                loggedInEmail.textContent = email;
            }}
            loginButton.addEventListener('click', () => {{
                const email = emailInput.value.trim();
                if (!email) {{ alert('请选择邮箱地址'); return; }}
                setCookie('vanna_email', email);
                loginContainer.classList.add('hidden');
                loggedInStatus.classList.remove('hidden');
                chatSections.classList.remove('hidden');
                loggedInEmail.textContent = email;
            }});
            logoutButton.addEventListener('click', () => {{
                deleteCookie('vanna_email');
                loginContainer.classList.remove('hidden');
                loggedInStatus.classList.add('hidden');
                chatSections.classList.add('hidden');
                emailInput.value = '';
            }});
            emailInput.addEventListener('keypress', (e) => {{
                if (e.key === 'Enter') loginButton.click();
            }});
        }});
    </script>

    <script>
        if (!customElements.get('vanna-chat')) {{
            setTimeout(() => {{
                if (!customElements.get('vanna-chat')) {{
                    document.querySelector('vanna-chat').innerHTML = '<div class="p-10 text-center text-gray-600"><h3 class="text-xl font-semibold mb-2">Vanna Chat 组件</h3><p>Web 组件加载失败，请检查网络连接。</p></div>';
                }}
            }}, 2000);
        }}
    </script>
</body>
</html>"""
