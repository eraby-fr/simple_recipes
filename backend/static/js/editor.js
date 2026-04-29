(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Tags preview
  // ---------------------------------------------------------------------------
  const tagsInput = document.getElementById("tags");
  const tagsPreview = document.getElementById("tags-preview");

  function renderTagsPreview() {
    if (!tagsInput || !tagsPreview) return;
    const raw = tagsInput.value;
    const tags = raw
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    tagsPreview.innerHTML = tags
      .map((t) => `<span class="tag">${escapeHtml(t)}</span>`)
      .join("");
  }

  if (tagsInput) {
    tagsInput.addEventListener("input", renderTagsPreview);
    renderTagsPreview();
  }

  // ---------------------------------------------------------------------------
  // Markdown editor helpers
  // ---------------------------------------------------------------------------
  const textarea = document.getElementById("content");

  window.insertMarkdown = function (before, after) {
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = textarea.value.substring(start, end);
    const replacement = before + (selected || "texte") + after;
    replaceSelection(replacement, start, end);
    const newCursor = start + before.length + (selected ? selected.length : 5);
    textarea.selectionStart = newCursor;
    textarea.selectionEnd = newCursor;
    textarea.focus();
    triggerPreview();
  };

  window.insertHeading = function () {
    if (!textarea) return;
    const start = textarea.selectionStart;
    const lineStart = textarea.value.lastIndexOf("\n", start - 1) + 1;
    const currentLine = textarea.value.substring(
      lineStart,
      textarea.value.indexOf("\n", start) === -1
        ? textarea.value.length
        : textarea.value.indexOf("\n", start)
    );
    const match = currentLine.match(/^(#{1,5}) /);
    let prefix;
    if (match) {
      prefix = match[1].length < 5 ? "#".repeat(match[1].length + 1) + " " : "## ";
      const newLine = currentLine.replace(/^#{1,5} /, prefix);
      const before = textarea.value.substring(0, lineStart);
      const after = textarea.value.substring(lineStart + currentLine.length);
      textarea.value = before + newLine + after;
    } else {
      prefix = "## ";
      const before = textarea.value.substring(0, lineStart);
      const after = textarea.value.substring(lineStart);
      textarea.value = before + prefix + after;
    }
    textarea.selectionStart = textarea.selectionEnd = lineStart + prefix.length;
    textarea.focus();
    triggerPreview();
  };

  // ---------------------------------------------------------------------------
  // Preview toggle (editor / split / preview only)
  // ---------------------------------------------------------------------------
  let previewMode = "split"; // "split" | "editor" | "preview"

  window.togglePreview = function () {
    const layout = document.getElementById("editor-layout");
    if (!layout) return;
    if (previewMode === "split") {
      previewMode = "editor";
      layout.classList.add("show-editor");
      layout.classList.remove("show-preview");
    } else if (previewMode === "editor") {
      previewMode = "preview";
      layout.classList.remove("show-editor");
      layout.classList.add("show-preview");
    } else {
      previewMode = "split";
      layout.classList.remove("show-editor", "show-preview");
    }
  };

  // ---------------------------------------------------------------------------
  // Textarea: auto-grow + tab key support
  // ---------------------------------------------------------------------------
  if (textarea) {
    textarea.addEventListener("keydown", function (e) {
      if (e.key === "Tab") {
        e.preventDefault();
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        textarea.value =
          textarea.value.substring(0, start) +
          "  " +
          textarea.value.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + 2;
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Image upload: trigger on file select
  // ---------------------------------------------------------------------------
  const fileInput = document.getElementById("file-upload");
  const uploadForm = document.getElementById("upload-form");

  if (fileInput && uploadForm) {
    fileInput.addEventListener("change", function () {
      if (fileInput.files.length > 0) {
        uploadForm.dispatchEvent(new Event("submit", { bubbles: true }));
        // Reset input so same file can be re-selected
        setTimeout(() => {
          fileInput.value = "";
        }, 500);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Copy markdown image link to clipboard + insert at cursor
  // ---------------------------------------------------------------------------
  window.copyMarkdownLink = function (filename, btn) {
    const link = `![](images/${filename})`;

    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      replaceSelection(link, start, end);
      textarea.selectionStart = textarea.selectionEnd = start + link.length;
      textarea.focus();
      triggerPreview();
    }

    navigator.clipboard.writeText(link).catch(() => {});

    const originalText = btn.innerHTML;
    btn.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg> Copié !';
    btn.classList.add("btn-primary");
    btn.classList.remove("btn-outline");
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.classList.remove("btn-primary");
      btn.classList.add("btn-outline");
    }, 2000);
  };

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  function replaceSelection(text, start, end) {
    textarea.value =
      textarea.value.substring(0, start) +
      text +
      textarea.value.substring(end);
  }

  function triggerPreview() {
    if (!textarea) return;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
