(() => {
  'use strict';
  const form = document.querySelector('#article_form');
  if (!form) return;
  let dirty = Boolean(form.querySelector('.errornote, .errorlist'));
  form.addEventListener('input', () => { dirty = true; });
  form.addEventListener('change', () => { dirty = true; });
  form.addEventListener('submit', () => { dirty = false; });
  window.addEventListener('beforeunload', event => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = '';
  });
})();
