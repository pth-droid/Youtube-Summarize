(() => {
  'use strict';
  const mobile = matchMedia('(max-width:850px)');
  let open = !mobile.matches;
  document.documentElement.classList.toggle('drawer-closed', !open);
  document.addEventListener('DOMContentLoaded', () => {
    const drawer = document.getElementById('workspace-drawer');
    const toggle = document.getElementById('drawer-toggle');
    const backdrop = document.getElementById('drawer-backdrop');
    function setOpen(value, focus = true) {
      open = value;
      document.documentElement.classList.toggle('drawer-closed', !open);
      document.documentElement.classList.toggle('drawer-modal', open && mobile.matches);
      toggle.setAttribute('aria-expanded', String(open));
      drawer.inert = !open;
      drawer.setAttribute('aria-hidden', String(!open));
      document.getElementById('main').inert = open && mobile.matches;
      backdrop.hidden = !(open && mobile.matches);
      if (focus) {
        if (open && mobile.matches) document.getElementById('drawer-close').focus();
        else if (!open) toggle.focus();
      }
    }
    toggle.addEventListener('click', () => setOpen(!open));
    document.getElementById('drawer-close').addEventListener('click', () => setOpen(false));
    backdrop.addEventListener('click', () => setOpen(false));
    drawer.addEventListener('click', event => {
      if (mobile.matches && event.target.closest('[data-view],.brand')) setOpen(false);
    });
    mobile.addEventListener('change', () => setOpen(!mobile.matches, false));
    document.addEventListener('keydown', event => {
      if (!open) return;
      if (event.key === 'Escape') { setOpen(false); return; }
      if (mobile.matches && event.key === 'Tab') {
        const items = [...drawer.querySelectorAll('button,a,summary,input,select,[tabindex="0"]')].filter(item => !item.disabled && item.getClientRects().length);
        const first = items[0], last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    });
    setOpen(open, false);
  });
})();
