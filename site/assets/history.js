(() => {
  'use strict';
  const section = document.getElementById('overview-history');
  if (!section || !('IntersectionObserver' in window) || !Element.prototype.animate) return;

  const details = section.querySelector(':scope > details');
  const items = [...section.querySelectorAll('.th-item')];
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const printing = window.matchMedia('print');
  const seen = new WeakSet();
  const active = new Map();

  function finish(item) {
    const animations = active.get(item);
    if (!animations) return;
    animations.forEach(animation => animation.cancel());
    active.delete(item);
  }

  function finishAll() {
    [...active.keys()].forEach(finish);
  }

  function linkedItem() {
    const id = location.hash.slice(1).split('/').pop();
    const target = document.getElementById(id);
    return target && section.contains(target) ? target.closest('.th-item') : null;
  }

  function show(item) {
    if (seen.has(item) || !details?.open) return;
    seen.add(item);
    observer.unobserve(item);
    if (reduced.matches || printing.matches || linkedItem() === item) return;

    const compact = window.innerWidth <= 760;
    const index = items.indexOf(item);
    const delay = compact || index === 0 ? 0 : (index - 1) % 2 * 65;
    const targets = [...item.querySelectorAll(':scope > .th-year, :scope > .th-facts')];
    const animations = targets.map((target, offset) => target.animate([
      { opacity: 0, transform: `translateY(${compact ? 10 : 16}px)` },
      { opacity: 1, transform: 'translateY(0)' }
    ], {
      duration: compact ? 450 : 560,
      delay: delay + offset * 50,
      easing: 'cubic-bezier(.22, 1, .36, 1)',
      fill: 'backwards'
    }));
    active.set(item, animations);
    Promise.all(animations.map(animation => animation.finished.catch(() => {})))
      .then(() => { if (active.get(item) === animations) active.delete(item); });
  }

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => { if (entry.isIntersecting) show(entry.target); });
  }, { threshold: 0, rootMargin: '0px 0px -7% 0px' });

  function observe() {
    if (!details?.open) return;
    items.forEach(item => { if (!seen.has(item)) observer.observe(item); });
  }

  details?.addEventListener('toggle', () => {
    if (details.open) observe();
    else {
      finishAll();
      observer.disconnect();
    }
  });
  section.addEventListener('focusin', event => {
    const item = event.target.closest('.th-item');
    if (item) { seen.add(item); observer.unobserve(item); finish(item); }
  });
  reduced.addEventListener('change', () => { if (reduced.matches) finishAll(); });
  window.addEventListener('hashchange', () => {
    const item = linkedItem();
    if (item) { seen.add(item); observer.unobserve(item); finish(item); }
  });
  window.addEventListener('beforeprint', finishAll);
  window.addEventListener('resize', finishAll, { passive: true });
  document.addEventListener('visibilitychange', () => { if (document.hidden) finishAll(); });
  observe();
})();
