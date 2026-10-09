/**
 * 编辑器预览用的轻量 Markdown 渲染（文档 06 第 3.3 节）。
 *
 * 【为什么不用 markdown-it 之类的库】
 * 文档 06 说得很明确：「预览是辅助；线上效果以后端渲染为准」。
 * 预览只需要让作者看清结构（标题、列表、代码块、链接、图片），
 * 不需要与后端 100% 一致。为此引入一个渲染库 + 一个净化库，
 * 会给后台包增加几十 KB，而收益只有「预览更精确」这一点。
 *
 * 【但它必须做净化 —— 这不是可选项】
 * 预览是用 v-html 渲染的，而 v-html 会执行 HTML。
 * 威胁不只是「作者自己写坏」：
 * 如果作者从别处复制一段 Markdown 粘进来（教程、别人的博客），
 * 里面可能藏着 <img src=x onerror=...>。后端会在**保存时**过滤掉它，
 * 但预览发生在保存之前 —— 那时脚本已经执行了。
 *
 * 所以这里的策略与后端一致：**先转义所有 HTML，再只对白名单结构放行**。
 * 我们生成 HTML 的方式是「自己拼标签」，输入侧只做转义，
 * 不做「解析 HTML」，因此不存在解析器差异导致的绕过。
 */

/** HTML 转义。所有进入输出的用户内容都必须先过这里 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * 只允许 http / https / mailto 链接。
 *
 * 【为什么必须检查协议】
 * `[点我](javascript:alert(1))` 是经典 XSS 载荷。
 * 转义只能处理 < > 这类字符，防不住这种「合法 Markdown 语法、
 * 但协议危险」的情况。
 *
 * 相对路径（/uploads/xxx.webp）也要放行 —— 图片上传返回的就是它。
 */
function safeUrl(raw: string): string | null {
  const url = raw.trim()
  if (!url) return null

  // 相对路径与锚点：直接放行
  if (url.startsWith('/') || url.startsWith('#') || url.startsWith('./')) {
    return url
  }

  // 绝对 URL 必须是我们认识的协议。
  // 用 a 标签的 href 属性做一次规范化，能识别出 `java\nscript:` 这类
  // 用空白字符绕过的写法（浏览器会忽略 URL 中的换行与制表符）。
  try {
    const probe = document.createElement('a')
    probe.href = url
    const protocol = probe.protocol.toLowerCase()
    if (protocol === 'http:' || protocol === 'https:' || protocol === 'mailto:') {
      return url
    }
  } catch {
    return null
  }

  // 能走到这里说明 href 被解析成了奇怪的协议，或者根本无法解析 —— 一律拒绝
  return null
}

/**
 * 行内元素：代码 → 图片 → 链接 → 粗体 → 斜体 → 删除线。
 *
 * 顺序不能随意交换：
 * - 代码优先，否则 `` `**not bold**` `` 里的星号会被当成粗体标记
 * - 图片在链接之前，否则 ![alt](url) 会先被链接规则匹配成 [alt](url)
 */
function renderInline(text: string): string {
  // 行内代码：先抽出来用占位符保护，避免其中内容被后续规则处理
  const codes: string[] = []
  let out = text.replace(/`([^`]+)`/g, (_m, code: string) => {
    codes.push(code)
    return `\u0000CODE${codes.length - 1}\u0000`
  })

  // 其余内容全部转义 —— 此时 out 里除了占位符都是纯文本
  out = escapeHtml(out)

  // 图片：![alt](url "title")
  out = out.replace(
    /!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;)?\)/g,
    (_m, alt: string, url: string, title: string | undefined) => {
      const href = safeUrl(url)
      if (!href) return `![${alt}]` // 协议不安全：降级成纯文本，不生成标签
      const titleAttr = title ? ` title="${title}"` : ''
      return `<img src="${escapeHtml(href)}" alt="${alt}"${titleAttr} loading="lazy">`
    },
  )

  // 链接：[text](url "title")
  out = out.replace(
    /\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;)?\)/g,
    (_m, label: string, url: string, title: string | undefined) => {
      const href = safeUrl(url)
      if (!href) return label
      // 站外链接加 rel：target="_blank" 的页面能通过 window.opener
      // 操作原页面（reverse tabnabbing）。noopener 切断这个引用。
      const isExternal = /^https?:/i.test(href)
      const attrs = isExternal ? ' target="_blank" rel="noopener noreferrer"' : ''
      const titleAttr = title ? ` title="${title}"` : ''
      return `<a href="${escapeHtml(href)}"${titleAttr}${attrs}>${label}</a>`
    },
  )

  // 粗体、斜体、删除线
  out = out
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
    .replace(/~~([^~]+)~~/g, '<del>$1</del>')

  // 还原行内代码
  out = out.replace(/\u0000CODE(\d+)\u0000/g, (_m, i: string) => {
    return `<code>${escapeHtml(codes[Number(i)])}</code>`
  })

  return out
}

/**
 * 逐行渲染块级结构。
 *
 * 用「状态机」而不是「先把整段按空行切开」：
 * 列表和代码块都可能包含空行，先切分会把它们切断。
 */
export function renderMarkdownPreview(source: string): string {
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  const html: string[] = []

  let inCode = false
  let codeLang = ''
  let codeLines: string[] = []

  // 列表状态：记录当前是哪种列表，遇到不同类型的行时先关闭
  let listType: 'ul' | 'ol' | null = null

  // 引用块
  let inQuote = false

  const closeList = (): void => {
    if (listType) {
      html.push(`</${listType}>`)
      listType = null
    }
  }
  const closeQuote = (): void => {
    if (inQuote) {
      html.push('</blockquote>')
      inQuote = false
    }
  }
  const closeAll = (): void => {
    closeList()
    closeQuote()
  }

  for (const line of lines) {
    // ---- 代码块 ----
    const fence = line.match(/^\s*```\s*(\S*)/)
    if (fence) {
      if (inCode) {
        const cls = codeLang ? ` class="language-${escapeHtml(codeLang)}"` : ''
        html.push(
          `<pre><code${cls}>${escapeHtml(codeLines.join('\n'))}</code></pre>`,
        )
        inCode = false
        codeLang = ''
        codeLines = []
      } else {
        closeAll()
        inCode = true
        codeLang = fence[1] ?? ''
      }
      continue
    }
    if (inCode) {
      codeLines.push(line)
      continue
    }

    // ---- 空行 ----
    if (!line.trim()) {
      closeAll()
      continue
    }

    // ---- 标题 ----
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      closeAll()
      const level = heading[1].length
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      continue
    }

    // ---- 分隔线 ----
    // 三个及以上**同一种**符号（- * _），中间可有空格，如 "- - -"。
    //
    // 【为什么不能把 \1 写进字符类】
    // 最初写的是 /^\s*([-*_])\s*\1\s*\1[\s\1]*$/，
    // 但字符类里的 \1 无效：TS 报「Octal escape sequences and
    // backreferences are not allowed in a character class」，
    // 运行时会变成八进制转义 \x01，匹配的是一堆控制字符。
    // 改成 [-*_\s]* 即「任意空白或分隔符号」。
    //
    // 同一种符号这个限制与 markdown 规范一致：
    // "-*-" 不是分隔线，而是一个普通段落。
    if (/^\s*([-*_])\s*\1\s*\1[-*_\s]*$/.test(line)) {
      closeAll()
      html.push('<hr>')
      continue
    }

    // ---- 引用 ----
    const quote = line.match(/^\s*>\s?(.*)$/)
    if (quote) {
      closeList()
      if (!inQuote) {
        html.push('<blockquote>')
        inQuote = true
      }
      html.push(`<p>${renderInline(quote[1])}</p>`)
      continue
    }
    closeQuote()

    // ---- 无序列表 ----
    const ul = line.match(/^\s*[-*+]\s+(.*)$/)
    if (ul) {
      if (listType !== 'ul') {
        closeList()
        html.push('<ul>')
        listType = 'ul'
      }
      html.push(`<li>${renderInline(ul[1])}</li>`)
      continue
    }

    // ---- 有序列表 ----
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (ol) {
      if (listType !== 'ol') {
        closeList()
        html.push('<ol>')
        listType = 'ol'
      }
      html.push(`<li>${renderInline(ol[1])}</li>`)
      continue
    }

    // ---- 普通段落 ----
    closeAll()
    html.push(`<p>${renderInline(line)}</p>`)
  }

  // 收尾：未闭合的代码块按代码块输出（写作中很常见，不能丢内容）
  if (inCode) {
    const cls = codeLang ? ` class="language-${escapeHtml(codeLang)}"` : ''
    html.push(`<pre><code${cls}>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
  }
  closeAll()

  return html.join('\n')
}

/**
 * 从 Markdown 里提取纯文本（用于字数统计）。
 *
 * 与后端的 strip_markdown 口径接近，但不要求一致 ——
 * 字数只是给作者的粗略参考，不影响任何存储内容。
 */
export function markdownPlainText(source: string): string {
  return source
    .replace(/```[\s\S]*?```/g, ' ') // 代码块整体去掉
    .replace(/`[^`]*`/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1') // 链接保留文字
    .replace(/^\s*#{1,6}\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+[.)]\s+/gm, '')
    .replace(/[*_~]/g, '')
    .replace(/\s+/g, '')
}
