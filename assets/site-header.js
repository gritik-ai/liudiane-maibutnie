(()=> {
  'use strict';
  const button = document.getElementById('siteMenuToggle');
  const nav = document.getElementById('siteNavLinks');
  if (!button || !nav) return;
  const closeMenu = () => {
    nav.classList.remove('is-open');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-label', 'Відкрити меню');
    button.textContent = '☰';
  };
  button.addEventListener('click', () => {
    const isOpen = nav.classList.toggle('is-open');
    button.setAttribute('aria-expanded', String(isOpen));
    button.setAttribute('aria-label', isOpen ? 'Закрити меню' : 'Відкрити меню');
    button.textContent = isOpen ? '×' : '☰';
  });
  nav.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenu();
  });
  document.addEventListener('click', event => {
    if (!nav.contains(event.target) && !button.contains(event.target)) closeMenu();
  });
})();