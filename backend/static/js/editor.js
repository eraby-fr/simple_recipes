(function () {
  "use strict";

  // Keep in sync with app.storage.safe_image_filename
  function safeImageFilename(name) {
    name = String(name).split(/[/\\]/).pop();
    return name.replace(/[^\w.\-]/g, "_");
  }

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

  function insertImageMarkdown(filename) {
    const link = `![](images/${filename})`;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const needsNewline =
      start > 0 && textarea.value.charAt(start - 1) !== "\n";
    const block = (needsNewline ? "\n\n" : "") + link + "\n\n";
    replaceSelection(block, start, textarea.selectionEnd);
    textarea.selectionStart = textarea.selectionEnd = start + block.length;
    triggerPreview();
  }

  function removeImageMarkdown(filename) {
    if (!textarea) return;
    const pattern = new RegExp(
      `\\n?\\n?!\\[[^\\]]*\\]\\(images/${escapeRegExp(filename)}\\)\\n?`,
      "g"
    );
    textarea.value = textarea.value.replace(pattern, "\n");
    triggerPreview();
  }

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
  // Textarea: tab key support
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
  // Image upload: auto-insert markdown; HTMX on edit, pending files on create
  // ---------------------------------------------------------------------------
  const fileInput = document.getElementById("file-upload");
  const uploadForm = document.getElementById("upload-form");
  const coverInput = document.getElementById("cover-image-input");
  const pendingList = document.querySelector(".pending-image-list");
  const isCreateMode = Boolean(coverInput);
  let pendingFiles = [];

  function syncPendingInput() {
    if (!fileInput || !isCreateMode) return;
    const dt = new DataTransfer();
    pendingFiles.forEach((f) => dt.items.add(f));
    fileInput.files = dt.files;
  }

  function setPendingCover(filename) {
    if (coverInput) coverInput.value = filename;
    renderPending();
  }

  function renderPending() {
    if (!pendingList) return;
    if (!pendingFiles.length) {
      pendingList.innerHTML =
        '<p class="no-images">Aucune image pour cette recette.</p>';
      return;
    }
    const cover = coverInput ? coverInput.value : "";
    pendingList.innerHTML =
      '<div class="image-grid">' +
      pendingFiles
        .map((file) => {
          const name = safeImageFilename(file.name);
          const url = URL.createObjectURL(file);
          const isCover = cover === name;
          return `<div class="image-item ${isCover ? "is-cover" : ""}">
            <div class="image-thumb"><img src="${url}" alt="${escapeHtml(name)}"></div>
            <div class="image-actions">
              <button type="button" class="btn-sm ${isCover ? "btn-primary" : "btn-outline"}"
                data-cover="${escapeHtml(name)}">${isCover ? "Couverture" : "Définir"}</button>
              <button type="button" class="btn-danger btn-sm" data-remove="${escapeHtml(name)}" aria-label="Retirer ${escapeHtml(name)}">×</button>
            </div>
            <code class="image-ref">![](images/${escapeHtml(name)})</code>
          </div>`;
        })
        .join("") +
      "</div>";
  }

  if (pendingList) {
    pendingList.addEventListener("click", function (e) {
      const coverBtn = e.target.closest("[data-cover]");
      if (coverBtn) {
        setPendingCover(coverBtn.getAttribute("data-cover"));
        return;
      }
      const removeBtn = e.target.closest("[data-remove]");
      if (removeBtn) {
        const name = removeBtn.getAttribute("data-remove");
        pendingFiles = pendingFiles.filter(
          (f) => safeImageFilename(f.name) !== name
        );
        removeImageMarkdown(name);
        if (coverInput && coverInput.value === name) {
          coverInput.value = pendingFiles.length
            ? safeImageFilename(pendingFiles[0].name)
            : "";
        }
        syncPendingInput();
        renderPending();
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", function () {
      const selected = Array.from(fileInput.files || []);
      if (!selected.length) return;

      selected.forEach((file) => {
        insertImageMarkdown(safeImageFilename(file.name));
      });

      if (isCreateMode) {
        selected.forEach((file) => pendingFiles.push(file));
        if (coverInput && !coverInput.value && pendingFiles.length) {
          coverInput.value = safeImageFilename(pendingFiles[0].name);
        }
        syncPendingInput();
        renderPending();
        return;
      }

      if (uploadForm) {
        uploadForm.dispatchEvent(new Event("submit", { bubbles: true }));
        setTimeout(() => {
          fileInput.value = "";
        }, 500);
      }
    });
  }

  if (isCreateMode) {
    renderPending();
  }

  // ---------------------------------------------------------------------------
  // Copy markdown image link to clipboard + insert at cursor
  // ---------------------------------------------------------------------------
  window.copyMarkdownLink = function (filename, btn) {
    const link = `![](images/${filename})`;

    insertImageMarkdown(filename);
    navigator.clipboard.writeText(link).catch(() => {});

    const originalText = btn.innerHTML;
    btn.textContent = "Copié !";
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
    if (!textarea) return;
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
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeRegExp(str) {
    return String(str).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }
})();
