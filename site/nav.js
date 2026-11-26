// AnalystOS header menus (Slice 130): hover or click to open on desktop, accordion in the phone drawer.
// Keyboard: Escape closes the open menu (or the drawer) and returns focus to its button; tabbing out of a
// menu closes it. Without this script the menus do not open; the footer still links every page's main sections.
(function () {
  var head = document.getElementById("an-head");
  if (!head) return;
  var items = [].slice.call(head.querySelectorAll(".an-has")), timer;
  function btn(li) { return li.querySelector("button"); }
  function close(li) { li.classList.remove("open"); li.hovered = false; btn(li).setAttribute("aria-expanded", "false"); }
  function closeAll(except) { items.forEach(function (li) { if (li !== except) close(li); }); }
  function open(li) { closeAll(li); li.classList.add("open"); btn(li).setAttribute("aria-expanded", "true"); }
  var wide = function () { return window.innerWidth > 860; };
  items.forEach(function (li) {
    btn(li).addEventListener("click", function () {
      clearTimeout(timer);
      if (li.hovered) { li.hovered = false; open(li); return; }  // a click right after hover-open keeps it open
      li.classList.contains("open") ? close(li) : open(li);
    });
    li.addEventListener("mouseenter", function () {
      if (!wide()) return;
      clearTimeout(timer);
      timer = setTimeout(function () { if (!li.classList.contains("open")) { open(li); li.hovered = true; } }, 90);
    });
    li.addEventListener("mouseleave", function () { if (wide()) { clearTimeout(timer); timer = setTimeout(function () { closeAll(); }, 160); } });
    li.addEventListener("focusout", function (e) { if (e.relatedTarget && !li.contains(e.relatedTarget)) close(li); });
  });
  var burger = head.querySelector(".an-burger");
  function closeDrawer() { head.classList.remove("nav-open"); burger.setAttribute("aria-expanded", "false"); }
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var openLi = items.filter(function (li) { return li.classList.contains("open"); })[0];
    if (openLi) { closeAll(); btn(openLi).focus(); return; }
    if (head.classList.contains("nav-open")) { closeDrawer(); burger.focus(); }
  });
  document.addEventListener("click", function (e) { if (!head.contains(e.target)) closeAll(); });
  head.addEventListener("click", function (e) { if (e.target.closest && e.target.closest(".an-mega a")) { closeAll(); closeDrawer(); } });
  burger.addEventListener("click", function () { var o = head.classList.toggle("nav-open"); burger.setAttribute("aria-expanded", String(o)); });
})();
