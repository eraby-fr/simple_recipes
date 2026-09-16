/* Home page: tag filter buttons.
 *
 * Tag values are read from the data-tag attribute rather than being inlined
 * into an onclick handler, so a tag can never be parsed as JavaScript.
 */
(function () {
  "use strict";

  function setTagFilter(tag, btn) {
    const input = document.getElementById("tag_filter");
    if (input) input.value = tag;
    document.querySelectorAll(".tag-btn").forEach(function (b) {
      b.classList.remove("active");
    });
    if (btn) btn.classList.add("active");
  }

  // Delegated: the tag list is re-rendered by htmx after a search.
  document.addEventListener("click", function (event) {
    const btn = event.target.closest(".tag-btn");
    if (!btn) return;
    setTagFilter(btn.dataset.tag || "", btn);
  });
})();
