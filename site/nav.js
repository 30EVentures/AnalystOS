// AnalystOS header menus (Slice 130): hover or click to open on desktop, accordion in the phone drawer.
// Keyboard: Escape closes, tabbing out of a menu closes it. Every link is also in the footer, so nothing needs this script.
(function () {
  var head = document.getElementById("an-head");
  if (!head) return;
  var items = [].slice.call(head.querySelectorAll(".an-has")), timer;
  function closeAll(except) {
    items.forEach(function (li) {
      if (li !== except) { li.classList.remove("open"); li.querySelector("button").setAttribute("aria-expanded", "false"); }
    });
  }
  function open(li) { closeAll(li); li.classList.add("open"); li.querySelector("button").setAttribute("aria-expanded", "true"); }
  var wide = function () { return window.innerWidth > 860; };
  items.forEach(function (li) {
    li.querySelector("button").addEventListener("click", function () { li.classList.contains("open") ? closeAll() : open(li); });
    li.addEventListener("mouseenter", function () { if (wide()) { clearTimeout(timer); timer = setTimeout(function () { open(li); }, 90); } });
    li.addEventListener("mouseleave", function () { if (wide()) { clearTimeout(timer); timer = setTimeout(function () { closeAll(); }, 160); } });
  });
  var burger = head.querySelector(".an-burger");
  function closeDrawer() { head.classList.remove("nav-open"); burger.setAttribute("aria-expanded", "false"); }
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeAll(); closeDrawer(); } });
  head.addEventListener("focusout", function (e) { if (e.relatedTarget && !head.contains(e.relatedTarget)) closeAll(); });
  document.addEventListener("click", function (e) { if (!head.contains(e.target)) closeAll(); });
  head.addEventListener("click", function (e) { if (e.target.closest && e.target.closest(".an-mega a")) { closeAll(); closeDrawer(); } });
  burger.addEventListener("click", function () { var o = head.classList.toggle("nav-open"); burger.setAttribute("aria-expanded", String(o)); });
})();
