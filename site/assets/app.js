(() => {
  'use strict';
  const copy = window.IR_COPY;
  const config = window.IR_CONFIG;
  const languageKey = 'dengi-ir-language';
  const root = document.documentElement;
  const header = document.querySelector('.ir-header');
  const subnav = document.querySelector('.ir-subnav');
  const hero = document.querySelector('.hero');
  const timeline = document.getElementById('timelineTrack');
  const previous = document.getElementById('tlPrev');
  const next = document.getElementById('tlNext');
  const sectionPicker = document.getElementById('investor-menu');
  const sectionCurrent = document.getElementById('investor-current');
  const sections = ['highlights', 'financials', 'funding', 'risk', 'strategy', 'documents', 'ir-contact'];
  const pages = [...document.querySelectorAll('[data-page-section]')];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let language = 'en';
  let activePage = 'home';
  let framePending = false;
  let revealObserver;
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  const text = key => copy[key]?.[language] || '';
  const motion = () => reducedMotion.matches ? 'instant' : 'smooth';
  const clamp = value => Math.max(0, Math.min(1, value));

  function renderTeam() {
    const caption = value => value?.[language] || value?.ru || value?.en || '';
    const captionLanguage = value => value?.[language] ? language : value?.ru ? 'ru' : 'en';
    const members = config.team.filter(member => member.photo);
    const grid = document.getElementById('team-grid');
    grid.replaceChildren();
    document.getElementById('team-section').hidden = members.length === 0;
    for (const member of members) {
      const card = document.createElement('article');
      card.className = 'team-card card';
      const photo = document.createElement('img');
      Object.assign(photo, { src: member.photo, alt: caption(member.photoAlt) || caption(member.name) || 'Dengi Market', loading: 'lazy', decoding: 'async', width: 320, height: 400 });
      photo.className = 'team-photo';
      photo.lang = captionLanguage(member.name);
      const portrait = document.createElement('div');
      portrait.className = 'team-portrait';
      portrait.append(photo);
      card.append(portrait);
      if (caption(member.name)) {
        const name = document.createElement('h3');
        name.textContent = caption(member.name);
        name.lang = captionLanguage(member.name);
        card.append(name);
      }
      if (caption(member.role)) {
        const role = document.createElement('p');
        role.className = 'team-role';
        role.textContent = caption(member.role);
        role.lang = captionLanguage(member.role);
        card.append(role);
      }
      if (member.email) {
        const email = document.createElement('a');
        email.className = 'team-email';
        email.dataset.teamEmail = '';
        email.textContent = member.email;
        email.href = `mailto:${member.email}`;
        email.lang = 'en';
        email.dir = 'ltr';
        card.append(email);
      }
      grid.append(card);
    }
  }

  function updateTimeline() {
    previous.disabled = timeline.scrollLeft <= 2;
    next.disabled = timeline.scrollLeft >= timeline.scrollWidth - timeline.clientWidth - 2;
  }

  function updateOffsets(headerHeight = header.offsetHeight, subnavHeight = subnav.offsetHeight) {
    root.style.setProperty('--header-height', `${headerHeight}px`);
    root.style.setProperty('--subnav-height', `${activePage === 'investors' ? subnavHeight : 0}px`);
  }

  function updateNavigation() {
    // Read geometry before changing classes or CSS properties during scrolling.
    const headerHeight = header.offsetHeight;
    const subnavHeight = subnav.offsetHeight;
    const offset = headerHeight + 48;
    let currentPage = 'home';
    for (const page of pages) {
      if (page.getBoundingClientRect().top <= offset) currentPage = page.dataset.pageSection;
    }
    const sectionOffset = headerHeight + subnavHeight + 48;
    let currentSection = 'highlights';
    for (const id of sections) {
      if (document.getElementById(id).getBoundingClientRect().top <= sectionOffset) currentSection = id;
    }
    if (activePage !== currentPage) {
      activePage = currentPage;
      updateTitle();
    }
    document.querySelectorAll('.site-nav-link').forEach(link => {
      const selected = link.dataset.section
        ? activePage === 'investors' && currentSection === link.dataset.section
        : link.dataset.page === activePage && !(activePage === 'investors' && currentSection === 'documents');
      link.classList.toggle('current', selected);
      if (selected) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
    document.querySelectorAll('.ir-subnav a').forEach(link => {
      const selected = link.hash === `#investors/${currentSection}`;
      link.classList.toggle('current', selected);
      if (selected) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
    sectionCurrent.textContent = sectionPicker.querySelector(`a[href="#investors/${currentSection}"]`).textContent;
    updateOffsets(headerHeight, subnavHeight);
  }

  function updateScrollScene() {
    framePending = false;
    const y = window.scrollY;
    const progress = window.IR_MOTION?.active ? 0 : clamp(y / Math.max(1, hero.offsetHeight));
    const reading = clamp(y / Math.max(1, document.documentElement.scrollHeight - innerHeight));
    updateNavigation();
    root.style.setProperty('--hero-progress', reducedMotion.matches ? '0' : progress.toFixed(4));
    root.style.setProperty('--reading-progress', reading.toFixed(4));
    header.classList.toggle('is-scrolled', y > 24);
  }

  function scheduleScrollScene() {
    if (!framePending) {
      framePending = true;
      requestAnimationFrame(updateScrollScene);
    }
  }

  function updateTitle() {
    document.title = text('seoTitle');
    document.querySelector('meta[name="description"]').content = text('seoDescription');
    document.querySelector('meta[property="og:title"]').content = text('seoTitle');
    document.querySelector('meta[property="og:description"]').content = text('seoDescription');
    document.querySelector('meta[property="og:locale"]').content = language === 'ru' ? 'ru_RU' : 'en_GB';
    const canonical = document.querySelector(`link[hreflang="${language}"]`).href;
    document.querySelector('link[rel="canonical"]').href = canonical;
    document.querySelector('meta[property="og:url"]').content = canonical;
  }

  function captureReadingPosition() {
    if (window.scrollY < 40) return null;
    const inset = header.offsetHeight + (activePage === 'investors' ? subnav.offsetHeight : 0);
    let anchor;
    for (const section of document.querySelectorAll('.hero, #featured-results, .advantages-section, section.block, #team-section, #ir-contact')) {
      if (section.getClientRects().length && section.getBoundingClientRect().top <= inset + 24) anchor = section;
    }
    return anchor ? { element: anchor, offset: documentTop(anchor) - window.scrollY - inset } : null;
  }

  function setLanguage(value, persist = true) {
    const readingPosition = persist ? captureReadingPosition() : null;
    const restartMotion = window.IR_MOTION?.active;
    if (restartMotion) window.IR_MOTION.destroy();
    language = value === 'ru' ? 'ru' : 'en';
    root.lang = language;
    for (const [key, translations] of Object.entries(copy)) {
      const element = document.getElementById(key);
      if (element) element.innerHTML = translations[language];
    }
    document.querySelectorAll('[data-copy]').forEach(element => element.innerHTML = text(element.dataset.copy));
    document.getElementById('h1').innerHTML = '<span class="hero-word-mask"><span class="hero-word">DENGI</span></span><span class="hero-word-mask"><span class="hero-word accent">MARKET</span></span>';
    const paragraphs = [...document.querySelectorAll('#heroSub p')];
    if (paragraphs[0]) {
      const value = paragraphs[0].textContent.replace(/^Dengi Market\s*(?:-\s*|is\s+)/, '').trim();
      const lead = value.charAt(0).toLocaleUpperCase(language) + value.slice(1);
      // Only split existing approved copy; do not rewrite or translate it.
      const splitAt = language === 'ru' ? lead.indexOf('. ') + 1 : lead.indexOf(', ') + 1;
      paragraphs[0].replaceChildren();
      if (splitAt > 0) {
        const line = document.createElement('span');
        line.className = 'hero-sub-line';
        line.textContent = lead.slice(0, splitAt);
        paragraphs[0].append(line, document.createTextNode(' ' + lead.slice(splitAt).trim()));
      } else paragraphs[0].textContent = lead;
    }
    document.getElementById('companyCopy').replaceChildren(...paragraphs.slice(1, 2));
    document.getElementById('companyContext').replaceChildren(...paragraphs.slice(2));
    document.querySelectorAll('#companyContext p').forEach((paragraph, index) => {
      const symbol = index === 0 ? 'i-wallet' : 'i-target';
      paragraph.insertAdjacentHTML('afterbegin', `<svg class="context-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#${symbol}"></use></svg>`);
    });
    document.querySelectorAll('[data-content-key]').forEach(details => {
      const heading = document.getElementById(details.dataset.contentKey).querySelector('h3');
      if (heading) details.querySelector('.summary-title').innerHTML = heading.innerHTML;
    });
    document.querySelectorAll('[data-language]').forEach(button => {
      const selected = button.dataset.language === language;
      button.classList.toggle('active', selected);
      if (selected) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    document.querySelector('.site-nav').setAttribute('aria-label', text('primaryNavigation'));
    subnav.setAttribute('aria-label', text('investorNavigation'));
    document.querySelector('.locale').setAttribute('aria-label', text('languageSelection'));
    previous.setAttribute('aria-label', text('previousEvent'));
    next.setAttribute('aria-label', text('nextEvent'));
    document.querySelector('.hero-art img').alt = text('heroAlt');
    document.querySelectorAll('[data-document-action]').forEach(link => {
      const year = link.getAttribute('href').match(/\d{4}/)[0];
      link.setAttribute('aria-label', `${text(link.dataset.documentAction === 'open' ? 'openDocument' : 'downloadDocument')} — ${year}`);
    });
    document.querySelectorAll('[data-localized-value]').forEach(element => {
      element.textContent = language === 'ru' ? element.dataset.ruValue : element.dataset.localizedValue;
    });
    document.querySelectorAll('[data-contact-email]').forEach(link => {
      link.textContent = config.contactEmail;
      link.href = `mailto:${config.contactEmail}`;
    });
    renderTeam();
    updateTitle();
    const selectedSection = sectionPicker.querySelector('a.current');
    if (selectedSection) sectionCurrent.textContent = selectedSection.textContent;
    updateOffsets();
    updateTimeline();
    if (restartMotion) window.IR_MOTION.init();
    if (readingPosition) {
      // При смене языка длина предыдущих блоков меняется; сохраняем место чтения.
      revealAncestors(readingPosition.element);
      const inset = header.offsetHeight + (activePage === 'investors' ? subnav.offsetHeight : 0);
      window.scrollTo({ top: Math.max(0, documentTop(readingPosition.element) - inset - readingPosition.offset), behavior: 'instant' });
    }
    scheduleScrollScene();
    if (persist) {
      const target = new URL(language === 'ru' ? 'index.ru.html' : './', location.href);
      target.hash = location.hash;
      if (target.href !== location.href) history.pushState(null, '', target);
      try { localStorage.setItem(languageKey, language); } catch { /* EN/RU also works without storage. */ }
    }
  }

  function documentTop(element) {
    let top = 0;
    for (let node = element; node; node = node.offsetParent) top += node.offsetTop;
    return top;
  }

  function revealAncestors(target) {
    window.IR_MOTION?.reveal(target);
    for (let node = target; node && node !== document.body; node = node.parentElement) {
      if (node.tagName === 'DETAILS' && !node.querySelector(':scope > summary').contains(target)) node.open = true;
      if (node.hasAttribute('data-reveal')) node.classList.add('is-revealed');
    }
  }

  function navigate({ initial = false, moveFocus = true } = {}) {
    const hash = location.hash.slice(1);
    const [requestedRoute, requestedAnchor] = hash.split('/');
    // Прежняя ссылка удалённой таблицы ведёт в сохранившийся раздел финансирования.
    const route = requestedRoute === 'covTitle' ? 'funding' : requestedRoute;
    const anchor = requestedAnchor === 'covTitle' ? 'funding' : requestedAnchor;
    const page = document.getElementById(`page-${route}`);
    const target = (page && anchor && page.contains(document.getElementById(anchor)) ? document.getElementById(anchor) : page)
      || document.getElementById(route) || document.getElementById('page-home');
    // Заголовок таблицы находится в summary; прежние прямые ссылки открывают её целиком.
    if (target.id === 'repaySchedTitle') target.closest('details').open = true;
    revealAncestors(target);
    // A financial-results link should expose the indicators, not just the chart.
    if (target.id === 'financials') target.querySelector('.financial-table-details').open = true;
    const owner = target.closest('[data-page-section]');
    const investorTarget = owner?.dataset.pageSection === 'investors' && target !== owner;
    requestAnimationFrame(() => {
      const top = target.id === 'page-home' ? 0 : documentTop(target) - header.offsetHeight - (investorTarget ? subnav.offsetHeight : 0) - 24;
      if (moveFocus) {
        const focusTarget = target.querySelector('h2, h3') || target;
        focusTarget.setAttribute('tabindex', '-1');
        focusTarget.focus({ preventScroll: true });
      }
      // При прямом входе ScrollTrigger не должен вернуть сохранённую до перехода позицию.
      if (initial) window.ScrollTrigger?.clearScrollMemory('manual');
      window.scrollTo({ top: Math.max(0, top), behavior: initial ? 'instant' : motion() });
      if (initial) window.ScrollTrigger?.update();
      updateScrollScene();
      updateTimeline();
    });
  }

  function initializeReveals() {
    if (window.IR_MOTION?.init({ intro: true })) return;
    const targets = [...document.querySelectorAll('[data-reveal]')];
    if (reducedMotion.matches || !('IntersectionObserver' in window)) {
      targets.forEach(target => target.classList.add('is-revealed'));
      return;
    }
    root.classList.add('motion-ready');
    revealObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-revealed');
          revealObserver.unobserve(entry.target);
        }
      }
    }, { threshold: 0, rootMargin: '0px 0px -8% 0px' });
    document.querySelectorAll('.featured-metric').forEach((target, index) => target.style.setProperty('--reveal-delay', `${index * 90}ms`));
    targets.forEach(target => revealObserver.observe(target));
  }

  document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click', event => {
    event.preventDefault();
    if (button.dataset.language !== language) setLanguage(button.dataset.language);
  }));
  document.querySelectorAll('details:not(.section-picker)').forEach(details => {
    details.addEventListener('toggle', () => {
      const body = details.querySelector(':scope > .disclosure-content');
      if (window.IR_MOTION?.active) {
        window.IR_MOTION.disclosure(details);
      } else if (body) {
        body.getAnimations().forEach(animation => animation.cancel());
        if (details.open && !reducedMotion.matches && body.animate) {
          body.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: 'ease-out' });
        }
      }
      updateTimeline();
      scheduleScrollScene();
    });
  });
  document.getElementById('skipContent').addEventListener('click', event => {
    event.preventDefault();
    const heading = document.getElementById('h1');
    heading.setAttribute('tabindex', '-1');
    heading.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: motion() });
  });
  document.querySelectorAll('a[href^="#"]:not(#skipContent)').forEach(link => link.addEventListener('click', () => {
    if (link.hash === location.hash) navigate();
  }));
  sectionPicker.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    sectionPicker.open = false;
  }));
  document.addEventListener('pointerdown', event => {
    if (!sectionPicker.contains(event.target)) sectionPicker.open = false;
  });
  document.addEventListener('focusin', event => {
    if (!sectionPicker.contains(event.target)) sectionPicker.open = false;
  });
  sectionPicker.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      sectionPicker.open = false;
      sectionPicker.querySelector('summary').focus();
    }
  });
  window.addEventListener('hashchange', () => navigate());
  window.addEventListener('scroll', scheduleScrollScene, { passive: true });
  window.addEventListener('resize', () => { updateOffsets(); updateTimeline(); scheduleScrollScene(); });
  document.addEventListener('focusin', event => revealAncestors(event.target));
  previous.addEventListener('click', () => timeline.scrollBy({ left: -timeline.clientWidth * 0.8, behavior: motion() }));
  next.addEventListener('click', () => timeline.scrollBy({ left: timeline.clientWidth * 0.8, behavior: motion() }));
  timeline.addEventListener('scroll', updateTimeline, { passive: true });
  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver(() => { updateOffsets(); updateTimeline(); scheduleScrollScene(); });
    observer.observe(header);
    observer.observe(subnav);
    observer.observe(timeline);
  }
  reducedMotion.addEventListener('change', () => {
    if (!window.IR_MOTION?.active) root.classList.toggle('motion-ready', !reducedMotion.matches);
    if (reducedMotion.matches) document.querySelectorAll('[data-reveal]').forEach(node => node.classList.add('is-revealed'));
    scheduleScrollScene();
  });
  window.addEventListener('beforeprint', () => {
    document.querySelectorAll('details:not(.section-picker)').forEach(details => {
      details.dataset.printOpen = String(details.open);
      details.open = true;
    });
  });
  window.addEventListener('afterprint', () => {
    document.querySelectorAll('details[data-print-open]').forEach(details => {
      details.open = details.dataset.printOpen === 'true';
      delete details.dataset.printOpen;
    });
  });

  // Язык задаётся адресом; сохранённое предпочтение не переопределяет индексируемую страницу.
  language = location.pathname.endsWith('/index.ru.html') ? 'ru' : 'en';
  window.addEventListener('popstate', () => {
    const nextLanguage = location.pathname.endsWith('/index.ru.html') ? 'ru' : 'en';
    // Переходы между разделами уже обрабатываются hashchange.
    // Не пересоздаём DOM и анимации, если язык не изменился.
    if (nextLanguage === language) return;
    setLanguage(nextLanguage, false);
    navigate({ initial: true, moveFocus: false });
  });
  setLanguage(language, false);
  initializeReveals();
  navigate({ initial: true, moveFocus: false });
})();
