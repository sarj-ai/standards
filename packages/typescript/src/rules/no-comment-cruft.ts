/**
 * @fileoverview Flag comment cruft — commented-out code, section banners, and
 * leading file-header comment preambles. Code carries the *what*; comments are
 * reserved for the *why*. The fuzzier "this comment merely restates the code"
 * judgment stays in review, not this rule — only these deterministic shapes are
 * flagged. JSDoc (`/** ... *\/`) is never flagged, and directive comments
 * (`eslint-`, `@ts-`, `prettier-`, `biome-`, `c8`, `<reference`, `TODO`,
 * `FIXME`) are ignored.
 */

import { ESLintUtils, type TSESTree } from "@typescript-eslint/utils";

type MessageIds = "commentedOutCode" | "sectionBanner" | "fileHeaderPreamble";
type Options = readonly [];

const LEADING_PREAMBLE_MIN = 4;

const DIRECTIVE_RE =
  /^(eslint\b|eslint-|@ts-|prettier-ignore|prettier\b|biome-|c8\b|v8\b|istanbul\b|@type\b|@vite|webpack|<reference|global\b|noinspection|todo\b|fixme\b|hack\b|xxx\b)/i;

const LICENSE_RE =
  /copyright|licen[cs]ed?|spdx|permission is hereby granted|all rights reserved/i;

const BANNER_FULL_RE = /^[\s\-=*#~_+.]{4,}$/;
// `={4,}` not `={3,}`: `===` is TS strict-equality and appears in prose comments.
const BANNER_RUN_RE = /={4,}|-{4,}|#{4,}|\*{4,}|~{4,}/;
const REGION_RE = /^#?(?:end)?region\b/i;

const CODE_KEYWORD_RE =
  /^(import |export |const |let |var |function\b|class |interface |type \w|enum |return\b|throw |await |async |if\s*\(|for\s*\(|while\s*\(|switch\s*\(|new |console\.)/;
const CODE_TAIL_RE = /[;{}()]\s*$|=>\s*$|,\s*$/;
// LHS must be a real identifier (not a number literal — `0=Monday` in prose is
// not an assignment) and `=` must not be `==`/`===`/`=>` (comparison/arrow).
const CALL_OR_ASSIGN_RE =
  /^[A-Za-z_$][\w.$[\]]*\s*(?:=(?![=>])|\+=|-=|\*=)\s*\S|^[A-Za-z_$][\w.$]*\([^)]*\)\s*;?\s*$/;

function stripCommentMarker(line: string): string {
  return line.replace(/^\s*\/\//, "").replace(/^\s*\*+/, "").trim();
}

function isDirective(text: string): boolean {
  return DIRECTIVE_RE.test(text.trim());
}

function isBanner(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  return BANNER_FULL_RE.test(t) || BANNER_RUN_RE.test(t) || REGION_RE.test(t);
}

function looksLikeCode(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  if (CODE_KEYWORD_RE.test(t) && CODE_TAIL_RE.test(t)) return true;
  return CALL_OR_ASSIGN_RE.test(t);
}

export default ESLintUtils.RuleCreator(
  (name) =>
    `https://github.com/sarj-ai/standards/blob/main/packages/typescript/src/rules/${name}.ts`,
)<Options, MessageIds>({
  name: "no-comment-cruft",
  meta: {
    type: "suggestion",
    docs: {
      description:
        "Flag commented-out code, section-banner comments, and leading file-header comment preambles.",
    },
    schema: [],
    messages: {
      commentedOutCode:
        "Commented-out code — delete it; git history remembers.",
      sectionBanner:
        "Section-banner / region comment — structure code with functions, not ASCII rules.",
      fileHeaderPreamble:
        "File-header comment preamble — use a brief doc comment for the why, not a block of `//` lines.",
    },
  },
  defaultOptions: [],
  create(context) {
    const sourceCode = context.sourceCode;

    function isStandalone(comment: TSESTree.Comment): boolean {
      const before = sourceCode.getTokenBefore(comment, {
        includeComments: false,
      });
      return !before || before.loc.end.line < comment.loc.start.line;
    }

    function isJsDoc(comment: TSESTree.Comment): boolean {
      return comment.type === "Block" && /^\*/.test(comment.value);
    }

    function reportLeadingPreamble(
      comments: readonly TSESTree.Comment[],
      firstCodeLine: number,
    ): void {
      const leading: TSESTree.Comment[] = [];
      let prevLine: number | null = null;
      for (const comment of comments) {
        if (comment.type !== "Line") break;
        if (comment.loc.start.line >= firstCodeLine) break;
        if (!isStandalone(comment)) break;
        const body = stripCommentMarker(comment.value);
        if (isDirective(body) || body.startsWith("!")) continue;
        if (prevLine !== null && comment.loc.start.line !== prevLine + 1) break;
        leading.push(comment);
        prevLine = comment.loc.start.line;
      }
      const first = leading[0];
      if (first === undefined || leading.length < LEADING_PREAMBLE_MIN) return;
      const isLicense = leading.some((c) =>
        LICENSE_RE.test(stripCommentMarker(c.value)),
      );
      if (!isLicense) {
        context.report({ node: first, messageId: "fileHeaderPreamble" });
      }
    }

    return {
      Program(): void {
        const comments = sourceCode.getAllComments();
        const firstCodeLine =
          sourceCode.ast.tokens[0]?.loc.start.line ?? Number.MAX_SAFE_INTEGER;

        for (const comment of comments) {
          if (isJsDoc(comment) || !isStandalone(comment)) continue;
          const texts = comment.value
            .split("\n")
            .map(stripCommentMarker)
            .filter((l) => l.length > 0 && !isDirective(l));
          if (texts.some(isBanner)) {
            context.report({ node: comment, messageId: "sectionBanner" });
          } else if (texts.some(looksLikeCode)) {
            context.report({ node: comment, messageId: "commentedOutCode" });
          }
        }

        reportLeadingPreamble(comments, firstCodeLine);
      },
    };
  },
});
