/* GSAP: постановка первого экрана, прокрутка и сравнение данных. */
(() => {
  'use strict';
  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;
  if (!gsap || !ScrollTrigger) return; // Базовая страница и CSS работают самостоятельно.
  gsap.registerPlugin(ScrollTrigger);

  const root = document.documentElement;
  const seen = new WeakSet();
  const scenes = new Map();
  const counted = new WeakSet();
  const counters = new Map();
  // GSAP 3.15.0 оставляет слушатели MediaQueryList после matchMedia().revert().
  // Храним три запроса на весь срок страницы; меняем только контекст анимаций.
  const queries = {
    wide: window.matchMedia('(min-width: 960px)'),
    reduced: window.matchMedia('(prefers-reduced-motion: reduce)'),
    print: window.matchMedia('print')
  };
  let media;
  let refreshTimer;
  let disclose;
  let introPending = false;
  function heroBackground(hero) {
    if (!hero.querySelector('.hero-lines') || !window.IntersectionObserver) return { start() {}, clear() {} };
    const events = new AbortController();
    const bounds = hero.getBoundingClientRect();
    let visible = bounds.bottom > 0 && bounds.top < window.innerHeight;
    let ready = false;
    const sync = () => {
      hero.classList.toggle('hero-background-running', ready && visible && !document.hidden);
    };
    hero.classList.add('hero-background-active');
    const observer = new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      sync();
    });
    observer.observe(hero);
    document.addEventListener('visibilitychange', sync, { signal: events.signal });
    sync();
    return {
      start() { ready = true; sync(); },
      clear() { events.abort(); observer.disconnect(); hero.classList.remove('hero-background-active', 'hero-background-running'); }
    };
  }

  function refresh() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => {
      // Safe refresh ждёт конца прокрутки и не обрывает переход по ссылке.
      if (media) ScrollTrigger.refresh(true);
    }, 100);
  }

  function overviewItems(overview) {
    return [...overview.querySelectorAll('.mvv-col--mission, .mvv-col--vision, #valuesTitle, .mini-value, #goalsH2, .goal-card, #companyFactsTitle, .fact-card')];
  }

  function finishFor(target) {
    // Ссылка может открыть details до того, как в нём зарегистрированы сцены.
    const overview = target.closest('#overview');
    if (overview) {
      const whole = target === overview || target.id === 'company-details';
      overviewItems(overview).forEach(item => {
        if (whole || item === target || item.contains(target)) {
          seen.add(item);
          scenes.get(item)?.progress(1).pause();
        }
      });
    }
    // Прямой переход к контакту сразу открывает и почтовое действие ниже заголовка.
    if (target.id === 'ir-contact') {
      const address = target.querySelector('.ir-contact-address');
      if (address) { seen.add(address); scenes.get(address)?.progress(1).pause(); }
    }
    for (const [container, animation] of scenes) {
      if (container === target || container.contains(target)) animation.progress(1).pause();
    }
    const control = target.closest('a, summary');
    if (control) counters.forEach((record, element) => {
      if (control.contains(element)) record.animation.progress(1).pause();
    });
  }

  function restoreCounters() {
    counters.forEach((record, element) => {
      element.textContent = record.finalText;
      element.classList.remove('count-value');
    });
    counters.clear();
  }

  function destroy() {
    clearTimeout(refreshTimer);
    if (media) {
      media.revert();
      // Повторный fromTo может вернуть startAt (opacity: 0) при revert.
      // Эти inline-свойства принадлежат только анимации раскрытия.
      document.querySelectorAll('details > .disclosure-content').forEach(body => {
        body.style.removeProperty('opacity');
        body.style.removeProperty('transform');
      });
    }
    restoreCounters();
    media = null;
    scenes.clear();
    disclose = null;
    root.classList.remove('gsap-motion');
  }

  function init({ intro = false } = {}) {
    destroy();
    introPending = intro;
    root.classList.remove('motion-ready');
    root.classList.add('gsap-motion');
    media = gsap.context(context => {
      const wide = queries.wide.matches;
      const reduced = queries.reduced.matches;
      const print = queries.print.matches;
      if (reduced || print) {
        introPending = false;
        return;
      }
      const distance = wide ? 28 : 12;
      const defaults = { duration: wide ? 0.75 : 0.5, ease: 'power3.out' };
      const interactionEvents = new AbortController();
      const disclosureAnimations = new Map();

      context.add('counters', scope => {
        scope.querySelectorAll('[data-count-value]').forEach(element => {
          if (counted.has(element) || counters.has(element) || !element.getClientRects().length) return;
          // Закрытые details не должны запускать счётчик до раскрытия.
          for (let parent = element.parentElement; parent; parent = parent.parentElement) {
            if (parent.tagName === 'DETAILS' && !parent.open && !parent.querySelector(':scope > summary').contains(element)) return;
          }
          const finalText = element.textContent;
          const value = Number(element.dataset.countValue);
          const decimals = Number(element.dataset.countDecimals || 0);
          const decimalSeparator = finalText.match(/\d+([.,])\d+/)?.[1] || '.';
          if (!Number.isFinite(value) || !/\d/.test(finalText)) return;
          const accessible = document.createElement('span');
          accessible.className = 'count-final';
          accessible.textContent = finalText;
          const display = document.createElement('span');
          display.className = 'count-display';
          display.setAttribute('aria-hidden', 'true');
          element.replaceChildren(accessible, display);
          element.classList.add('count-value');
          const state = { value: 0 };
          const render = () => {
            const number = state.value.toFixed(decimals).replace('.', decimalSeparator);
            const formatted = finalText.replace(/\d+(?:[.,]\d+)?/, number);
            if (display.textContent !== formatted) display.textContent = formatted;
          };
          const animation = gsap.to(state, {
            value, duration: wide ? 1.4 : 1.05, ease: 'power2.out', paused: true,
            onStart: () => counted.add(element),
            onUpdate: render,
            onComplete: () => { display.textContent = finalText; counted.add(element); }
          });
          const record = { finalText, animation, trigger: null };
          counters.set(element, record);
          render();
          record.trigger = ScrollTrigger.create({
            trigger: element, start: 'top 92%', once: true,
            onEnter: () => animation.play(),
            onEnterBack: () => animation.progress(1),
            onLeave: () => animation.progress(1)
          });
        });
      });
      context.counters(document);

      // Создаём сцены сверху вниз. Уже прочитанное не прячется при EN/RU и resize.
      function scene(container, build) {
        if (!container || seen.has(container)) return;
        const animation = gsap.timeline({
          paused: true,
          defaults,
          onStart: () => seen.add(container),
          onComplete: () => seen.add(container)
        });
        build(animation);
        scenes.set(container, animation);
        ScrollTrigger.create({
          trigger: container,
          start: 'top 88%',
          once: true,
          onEnter: () => animation.play(),
          onLeave: () => animation.progress(1)
        });
      }

      const hero = document.querySelector('.hero');
      const background = heroBackground(hero);
      if (introPending && (!location.hash || location.hash === '#home') && window.scrollY < 40) {
        const introTimeline = gsap.timeline({ id: 'hero-intro', defaults, onStart: () => seen.add(hero), onComplete: () => background.start() });
        scenes.set(hero, introTimeline);
        const title = hero.querySelector('.hero-title');
        // Слово появляется целиком: без поворотов, масок и зависимости от ширины шрифта.
        introTimeline.addLabel('brand', 0)
          .from(title, { opacity: 0, y: wide ? 20 : 12, duration: 0.8, ease: 'power3.out', clearProps: 'transform,opacity' }, 'brand')
          .from('.hero-sub', { opacity: 0, y: 10, duration: 0.55, clearProps: 'transform,opacity' }, 'brand+=0.25')
          .from('.hero-actions', { opacity: 0, y: 8, duration: 0.5, clearProps: 'transform,opacity' }, 'brand+=0.45');
        // Ссылки остаются доступны во время вступления; фокус завершает сцену.
        hero.addEventListener('focusin', () => introTimeline.progress(1).pause(), { signal: interactionEvents.signal });
        window.addEventListener('scroll', () => {
          if (window.scrollY > 60) introTimeline.progress(1).pause();
        }, { passive: true, signal: interactionEvents.signal });
      } else background.start();
      introPending = false;

      if (wide) {
        const departure = gsap.timeline({
          defaults: { ease: 'none' },
          scrollTrigger: { id: 'hero-depth', trigger: hero, start: 'top top', end: 'bottom top', scrub: 0.4 }
        });
        departure.to('.hero-copy', { y: -30, opacity: 0.82 }, 0);
        // Контур кнопки и секция масштабируются вместе, сохраняя общий стык.
        gsap.fromTo('.results-stage-frame', { scale: 0.94 }, {
          scale: 1, ease: 'none',
          scrollTrigger: { id: 'results-expand', trigger: '.results-stage', start: 'top 95%', end: 'top 38%', scrub: 0.35 }
        });
      }

      const results = document.getElementById('featured-results');
      scene(results, tl => {
        tl.from(results.querySelector('.stage-heading'), { opacity: 0, y: distance }, 0)
          .from(results.querySelectorAll('.featured-label'), { opacity: 0, y: 12, stagger: 0.09 }, 0.12)
          .from(results.querySelectorAll('.metric-value-mask'), { y: 12, opacity: 0.3, stagger: 0.08, duration: 0.55 }, 0.1)
          .from(results.querySelectorAll('.metric-rule'), { scaleX: 0, stagger: 0.14, transformOrigin: 'left center' }, 0.3);
      });

      document.querySelectorAll('.advantage-card').forEach(card => {
        const summary = card.querySelector(':scope > summary');
        scene(card, tl => tl.from(summary, {
          opacity: 0, y: wide ? 24 : 12, duration: 0.65
        }));
        const icon = summary.querySelector('.icon-hover');
        const press = summary.querySelector('.icon-press');
        if (!icon || !press) return;

        // Разные вложенные группы: наведение и нажатие не спорят за transform.
        gsap.set([icon, press], { transformOrigin: '50% 50%' });
        const hover = gsap.timeline({ paused: true, defaults: { duration: 0.32, ease: 'power2.out' } });
        hover.to(icon, { y: -3, scale: 1.025 }, 0);
        const hand = icon.querySelector('[data-icon-part="hand"]');
        if (hand) hover.to(hand, { rotation: 26, svgOrigin: '64 64', duration: 0.5 }, 0);
        const nodes = icon.querySelectorAll('[data-icon-part="node"]');
        if (nodes.length) hover.to(nodes, { scale: 1.3, transformOrigin: '50% 50%', stagger: 0.025 }, 0);
        const windows = icon.querySelector('[data-icon-part="windows"]');
        if (windows) hover.to(windows, { opacity: 0.75 }, 0);
        const lens = icon.querySelector('[data-icon-part="lens"]');
        if (lens) hover.to(lens, { x: -5, y: 2, rotation: -5, transformOrigin: '50% 50%' }, 0);
        const phone = icon.querySelector('[data-icon-part="phone"]');
        if (phone) hover.to(phone, { y: -4, rotation: 3, transformOrigin: '50% 50%' }, 0);
        const bullion = icon.querySelector('[data-icon-part="bullion"]');
        if (bullion) hover.to(bullion, { x: -2, y: 1, rotation: -2, transformOrigin: '50% 100%' }, 0.04);
        const terminals = icon.querySelectorAll('[data-icon-part="terminal"]');
        if (terminals.length) hover.to(terminals, { scale: 1.12, transformOrigin: '50% 50%', stagger: 0.035 }, 0);
        const code = icon.querySelector('[data-icon-part="code"]');
        if (code) hover.to(code, { scale: 1.08, transformOrigin: '50% 50%' }, 0.05);

        const tap = gsap.timeline({ paused: true });
        tap.to(press, { scale: 0.94, duration: 0.08, ease: 'power1.out' })
          .to(press, { scale: 1.045, duration: 0.17, ease: 'power2.out' })
          .to(press, { scale: 1, duration: 0.23, ease: 'power2.out' });
        let pointerOver = summary.matches(':hover') && window.matchMedia('(any-hover: hover)').matches;
        const updateHover = () => {
          if (pointerOver || summary.matches(':focus-visible')) hover.play();
          else hover.reverse();
        };
        const options = { signal: interactionEvents.signal };
        summary.addEventListener('pointerenter', event => {
          pointerOver = event.pointerType !== 'touch' && window.matchMedia('(any-hover: hover)').matches;
          updateHover();
        }, options);
        summary.addEventListener('pointerleave', () => { pointerOver = false; updateHover(); }, options);
        summary.addEventListener('pointercancel', () => { pointerOver = false; updateHover(); }, options);
        summary.addEventListener('focus', updateHover, options);
        summary.addEventListener('blur', updateHover, options);
        // Нативный click приходит от мыши, касания, Enter и пробела.
        summary.addEventListener('click', () => tap.restart(), options);
        updateHover();
      });

      // Орнамент движется только вместе с прокруткой, без автономных циклов.
      document.querySelectorAll('.scroll-ornament').forEach(ornament => {
        gsap.fromTo(ornament, { y: 16, scale: 0.97, opacity: 0.035 }, {
          y: -16, scale: 1.035, opacity: 0.11, ease: 'none',
          scrollTrigger: {
            trigger: ornament.closest('.advantage-card') || ornament.parentElement, start: 'top bottom', end: 'bottom top', scrub: 0.8
          }
        });
      });

      const about = document.querySelector('.about-intro');
      scene(about, tl => {
        tl.from(about.querySelector('h2'), { opacity: 0, y: distance }, 0)
          .from(about.querySelector('.hero-art'), { scale: 0.92, y: distance, opacity: 0, duration: 0.9 }, 0.08);
      });

      const overview = document.getElementById('overview');
      const overviewDetails = overview?.querySelector(':scope > details');
      const overviewScenes = new Map();
      function finishOverview() {
        // Скрытые числа не отрабатывают в закрытом details; непрочитанные
        // можно зарегистрировать заново, уже начатые остаются конечными.
        counters.forEach((record, element) => {
          if (!overview.contains(element)) return;
          record.animation.kill();
          record.trigger?.kill();
          // При закрытии до появления тоже завершаем число: повторное открытие
          // не должно создавать новые обёртки и удерживать старые в context.
          counted.add(element);
          element.textContent = record.finalText;
          element.classList.remove('count-value');
          counters.delete(element);
        });
        overviewScenes.forEach((record, item) => {
          record.animation.progress(1).pause().kill();
          record.trigger.kill();
          seen.add(item);
          scenes.delete(item);
        });
        overviewScenes.clear();
      }
      // Только открытый details имеет действительные координаты для ScrollTrigger.
      context.add('overview', () => {
        if (!overviewDetails?.open) return;
        overviewItems(overview).forEach((item, index) => {
          if (seen.has(item) || overviewScenes.has(item)) return;
          const fact = item.matches('.fact-card');
          const targets = fact ? item.querySelectorAll('.n, .l') : item;
          const lag = item.matches('.mvv-col--vision') ? 0.12
            : item.matches('.mini-value') ? [...item.parentElement.children].indexOf(item) * 0.07
            : item.matches('.goal-card') ? [...item.parentElement.children].indexOf(item) % 2 * 0.08
            : fact ? [...item.parentElement.children].indexOf(item) % 4 * 0.06 : 0;
          const animation = gsap.timeline({
            id: `overview-reveal-${index}`,
            paused: true,
            onStart: () => seen.add(item),
            onComplete: () => seen.add(item)
          }).from(targets, {
            opacity: 0, y: wide ? 22 : 12,
            duration: wide ? 0.7 : 0.5, ease: 'power2.out',
            stagger: fact ? 0.05 : 0, clearProps: 'opacity,transform'
          }, lag);
          scenes.set(item, animation);
          const trigger = ScrollTrigger.create({
            id: `overview-enter-${index}`,
            trigger: item, start: 'top 90%', once: true,
            onEnter: () => animation.play(),
            onEnterBack: () => animation.progress(1).pause(),
            onLeave: () => animation.progress(1).pause()
          });
          overviewScenes.set(item, { animation, trigger });
        });
      });
      context.overview();

      const team = document.getElementById('team-section');
      if (team && !team.hidden) {
        scene(team, tl => {
          tl.from(team.querySelectorAll('.team-title, .team-caption'), { opacity: 0, y: distance, stagger: 0.08, clearProps: 'opacity,transform' }, 0)
            .from(team.querySelectorAll('.team-card'), { opacity: 0, y: wide ? 24 : 12, stagger: wide ? 0.09 : 0.06, duration: 0.7, clearProps: 'opacity,transform' }, 0.15);
        });
      }

      const flow = document.querySelector('.flow');
      scene(flow, tl => tl.from(flow.children, { opacity: 0, y: distance, stagger: 0.1 }));

      const growth = document.querySelector('.growth-chart');
      scene(growth, tl => tl.from(growth.querySelectorAll('.growth-bar'), {
        scaleY: 0, transformOrigin: 'center bottom', duration: 0.85,
        stagger: { each: 0.045 }, ease: 'power2.out'
      }));
      const funding = document.querySelector('#funding .chart-scroll');
      scene(funding, tl => tl.from(funding.querySelectorAll('.track-bar i'), {
        scaleX: 0, transformOrigin: 'left center', duration: 0.8, stagger: 0.12
      }));
      const documents = document.querySelector('.doc-list');
      scene(documents, tl => tl.from(documents.children, { y: distance, opacity: 0, stagger: 0.09 }));

      const contact = document.getElementById('ir-contact');
      scene(contact, tl => {
        tl.from(contact.querySelectorAll('.ir-contact-kicker, h2, #irContactIntro, .ir-contact-resources'), {
          y: wide ? 20 : 12, opacity: 0, duration: 0.65, stagger: 0.08,
          clearProps: 'opacity,transform'
        }, 0);
      });
      const address = contact.querySelector('.ir-contact-address');
      scene(address, tl => {
        tl.from(contact.querySelector('.ir-contact-symbol'), { y: 10, opacity: 0, duration: 0.45, clearProps: 'opacity,transform' }, 0)
          .from(address.children, { y: wide ? 16 : 10, opacity: 0, duration: 0.65, stagger: 0.08, clearProps: 'opacity,transform' }, 0.05)
          .from(contact.querySelector('.ir-contact-signature'), { opacity: 0, duration: 0.45, clearProps: 'opacity' }, 0.25);
        const sheen = contact.querySelector('.ir-contact-sheen');
        if (sheen) {
          tl.fromTo(sheen, { xPercent: -110 }, { xPercent: 110, duration: 1.2, ease: 'power1.inOut' }, 0.1)
            .fromTo(sheen, { opacity: 0 }, { opacity: 0.24, duration: 0.25, ease: 'power1.out' }, 0.1)
            .to(sheen, { opacity: 0, duration: 0.25, ease: 'power1.in', clearProps: 'opacity,transform' }, 1.05);
        }
      });

      // Поздние анимации принадлежат context и отменяются при смене режима.
      context.add('disclosure', details => {
        const body = details.querySelector(':scope > .disclosure-content');
        if (!body) return;
        if (details === overviewDetails) {
          if (details.open) { context.overview(); context.counters(body); }
          else finishOverview();
          return;
        }
        if (details.open) {
          let animation = disclosureAnimations.get(body);
          if (!animation) {
            animation = gsap.fromTo(body, { opacity: 0, y: 6 }, {
              opacity: 1, y: 0, duration: 0.24, ease: 'power2.out',
              clearProps: 'opacity,transform', paused: true, immediateRender: false
            });
            disclosureAnimations.set(body, animation);
          }
          animation.restart();
          context.counters(body);
        } else {
          disclosureAnimations.get(body)?.progress(1).pause();
          counters.forEach((record, element) => {
            if (body.contains(element)) record.animation.progress(1).pause();
          });
        }
      });
      disclose = context.disclosure;
      return () => { interactionEvents.abort(); background.clear(); overviewScenes.clear(); disclosureAnimations.clear(); restoreCounters(); scenes.clear(); disclose = null; };
    }, document.body);
    refresh();
    return true;
  }

  window.IR_MOTION = {
    get active() { return Boolean(media); },
    init, destroy, refresh,
    reveal: finishFor,
    disclosure(details) { disclose?.(details); refresh(); }
  };
  document.fonts?.ready.then(refresh);
  Object.values(queries).forEach(query => query.addEventListener('change', () => {
    if (media) init();
  }));
  window.addEventListener('load', refresh);
  window.addEventListener('beforeprint', () => {
    scenes.forEach(animation => animation.progress(1).pause());
    counters.forEach(record => record.animation.progress(1).pause());
  });
})();
