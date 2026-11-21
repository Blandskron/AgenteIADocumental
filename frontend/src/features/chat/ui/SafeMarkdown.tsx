import type { ReactNode } from "react";

interface InlineOptions {
  onCitationClick?: (sourceIndex: number) => void;
  sourceCount?: number;
}

const INLINE_TOKEN_RE =
  /(\[Fuente\s+(\d+)\]|`([^`\n]+)`|\*\*([^*\n]+)\*\*|\*([^*\n]+)\*)/gi;

export function renderInlineMarkdown(
  text: string,
  options: InlineOptions = {},
): ReactNode[] {
  const { onCitationClick, sourceCount = 0 } = options;
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let keyCounter = 0;

  INLINE_TOKEN_RE.lastIndex = 0;
  while ((match = INLINE_TOKEN_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const [full, , citationNum, codeText, boldText, italicText] = match;
    if (citationNum) {
      const idx = Number(citationNum) - 1;
      if (onCitationClick && idx >= 0 && idx < sourceCount) {
        nodes.push(
          <button
            key={`cit-${keyCounter++}`}
            type="button"
            className="citation-chip"
            onClick={() => onCitationClick(idx)}
            aria-label={`Ver Fuente ${citationNum}`}
          >
            Fuente {citationNum}
          </button>,
        );
      } else {
        nodes.push(
          <span key={`cit-${keyCounter++}`} className="citation-chip static">
            {full}
          </span>,
        );
      }
    } else if (codeText !== undefined) {
      nodes.push(<code key={`code-${keyCounter++}`}>{codeText}</code>);
    } else if (boldText !== undefined) {
      nodes.push(<strong key={`b-${keyCounter++}`}>{boldText}</strong>);
    } else if (italicText !== undefined) {
      nodes.push(<em key={`i-${keyCounter++}`}>{italicText}</em>);
    }
    lastIndex = INLINE_TOKEN_RE.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

/**
 * Renders a safe subset of Markdown (headings, paragraphs, lists, fenced code, inline bold/italic/code,
 * and clickable [Fuente N] citations) using pure React elements — never innerHTML — eliminating XSS.
 */
export function SafeMarkdown({
  content,
  onCitationClick,
  sourceCount = 0,
}: {
  content: string;
  onCitationClick?: (sourceIndex: number) => void;
  sourceCount?: number;
}) {
  const normalized = (content || "").replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let blockKey = 0;
  const inlineOpts = { onCitationClick, sourceCount };

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    // Fenced code block
    if (line.trim().startsWith("```")) {
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length) i += 1;
      blocks.push(
        <pre key={`pre-${blockKey++}`} className="md-code-block">
          <code>{codeLines.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // Heading (# .. ###)
    const headingMatch = /^(#{1,4})\s+(.+)$/.exec(line.trim());
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const headingContent = renderInlineMarkdown(text, inlineOpts);
      if (level === 1) {
        blocks.push(
          <h3 key={`h-${blockKey++}`} className="md-heading">
            {headingContent}
          </h3>,
        );
      } else {
        blocks.push(
          <h4 key={`h-${blockKey++}`} className="md-heading">
            {headingContent}
          </h4>,
        );
      }
      i += 1;
      continue;
    }

    // Unordered list
    if (/^\s*[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        const itemText = lines[i].replace(/^\s*[-*]\s+/, "");
        items.push(
          <li key={`li-${blockKey++}`}>
            {renderInlineMarkdown(itemText, inlineOpts)}
          </li>,
        );
        i += 1;
      }
      blocks.push(
        <ul key={`ul-${blockKey++}`} className="md-list">
          {items}
        </ul>,
      );
      continue;
    }

    // Ordered list
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        const itemText = lines[i].replace(/^\s*\d+\.\s+/, "");
        items.push(
          <li key={`oli-${blockKey++}`}>
            {renderInlineMarkdown(itemText, inlineOpts)}
          </li>,
        );
        i += 1;
      }
      blocks.push(
        <ol key={`ol-${blockKey++}`} className="md-list">
          {items}
        </ol>,
      );
      continue;
    }

    // Paragraph
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("```") &&
      !/^(#{1,4})\s+/.test(lines[i].trim()) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i])
    ) {
      paraLines.push(lines[i]);
      i += 1;
    }
    blocks.push(
      <p key={`p-${blockKey++}`} className="md-paragraph">
        {renderInlineMarkdown(paraLines.join(" "), inlineOpts)}
      </p>,
    );
  }

  return <div className="safe-markdown">{blocks}</div>;
}
