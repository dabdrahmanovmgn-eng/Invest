(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const copy = {
    en: {
      setupTitle: 'Your first sign-in', setupIntro: 'Create your editor account to start publishing articles and photographs.',
      setupOnce: 'Keep your username and password for future sign-ins. This setup is only needed once.',
      setupHeading: 'Create an account', setupUsernameHint: 'At least 3 characters: Latin letters, numbers, dot, underscore, @ or hyphen.',
      setupPasswordHint: 'Choose a password with at least 12 characters.', confirmPassword: 'Repeat password',
      createAccount: 'Create account & sign in', creatingAccount: 'Creating account…',
      invalid_username: 'Use 3–64 Latin letters, numbers, dot, underscore, @ or hyphen for your username.',
      weak_password: 'Choose a password with 12–1024 characters.', passwordMismatch: 'The passwords do not match. Enter them again.',
      setup_complete: 'An account has already been created. Sign in with your username and password.',
      invalid_setup_token: 'The setup session has refreshed. Enter your password again and retry.',
      skip: 'Skip to content', uiLanguage: 'Interface language', viewArticles: 'Articles on the website', logout: 'Sign out',
      editorKicker: 'Dengi Market publications', pageTitle: 'Article editor', connecting: 'Connecting to the editor…',
      loginTitle: 'Your publishing workspace', loginIntro: 'Write articles, add photographs and publish updates on the website.',
      signIn: 'Sign in', signingIn: 'Signing in…', username: 'Username', password: 'Password', firstLogin: 'First sign-in',
      setupHelp: 'Create an administrator account in the project terminal. The command asks for a password.',
      workspace: 'Articles workspace', yourArticles: 'Articles', newArticle: 'New article', editArticle: 'Edit article',
      findArticle: 'Find an article', filterStatus: 'Status', allStatuses: 'All statuses', draft: 'Draft', published: 'Published', archived: 'Archived', retry: 'Try again',
      articleFields: 'Article details', openPublished: 'View publication', titleLabel: 'Title', articleLanguage: 'Article language',
      slugLabel: 'Page address', slugHint: 'Leave blank to create an address automatically. Use lowercase Latin letters, numbers and hyphens.',
      excerptLabel: 'Short introduction', excerptHint: 'Shown in the list of articles. Up to 600 characters.', bodyLabel: 'Article text',
      bodyHint: 'Write in plain text. Separate paragraphs with an empty line.', coverTitle: 'Cover image', coverHint: 'The main image for the article and its card.',
      chooseCover: 'Upload cover', imagesTitle: 'Photographs', imagesHint: 'Up to 12 images, shown after the article text.', chooseImages: 'Add images',
      fileHint: 'PNG, JPEG or WebP. Up to 8 MB per image.', archiveAction: 'Archive', saveDraft: 'Save draft', unpublishAction: 'Unpublish', publishAction: 'Publish', updatePublication: 'Update publication',
      discardTitle: 'Save your changes?', discardCopy: 'This article has unsaved changes. You can continue editing or leave without saving.',
      continueEditing: 'Continue editing', discardAction: 'Leave without saving', signedInAs: 'Signed in as',
      loadingList: 'Loading articles…', noArticles: 'No articles yet. Start with a new article.', noMatches: 'No articles match these filters.',
      listFailed: 'Could not load the articles.', articleCount: 'Articles', unsaved: 'You have unsaved changes.', savedDraft: 'Draft saved.', savedPublished: 'The article is published on the website.', savedArchived: 'The article is archived and is no longer visible on the website.',
      saving: 'Saving…', publishing: 'Publishing…', unpublishing: 'Unpublishing…', savedUnpublished: 'The article is no longer visible on the website. It is saved as a draft.', archiving: 'Archiving…', uploading: 'Uploading images…',
      coverAlt: 'Article cover', imageAlt: 'Article image', remove: 'Remove', removeCover: 'Remove cover', removeImage: 'Remove image',
      titleRequired: 'Enter a title before saving.', bodyRequired: 'Add the article text before publishing.', slugInvalid: 'Use lowercase Latin letters, numbers and single hyphens, up to 120 characters.',
      imageFormat: 'Choose a PNG, JPEG or WebP image.', imageSize: 'Each image must be no larger than 8 MB.', imageCount: 'You can add up to 12 photographs.',
      fileRead: 'The image could not be read. Choose it again.', imageResponse: 'The server returned an invalid image address.',
      offline: 'Could not connect to the editor. Open this page on the CMS server at http://127.0.0.1:8345/admin/.',
      invalid_credentials: 'The username or password is incorrect.', authentication_required: 'Your session has ended. Sign in again; the unsaved article is still here.',
      invalid_csrf: 'The session has been refreshed. Try the action again.', rate_limited: 'Too many sign-in attempts. Wait a minute and try again.',
      slug_exists: 'This page address is already in use. Choose another one.', image_too_large: 'The image must be no larger than 8 MB.', unsupported_image: 'Only PNG, JPEG and WebP images are supported.',
      mime_mismatch: 'The file format does not match its contents. Export it as PNG, JPEG or WebP.', storage_error: 'The server could not save the data. Try again.',
      serverRejected: 'The server could not complete this action. Check the fields and try again.', failedResponse: 'The server returned an unexpected response.',
      loggedOut: 'You have signed out.', setupNeeded: 'An administrator account has not been created yet. Follow the first sign-in instructions below.'
    },
    ru: {
      setupTitle: 'Первый вход в редактор', setupIntro: 'Создайте свой аккаунт, чтобы добавлять статьи и фотографии на сайт.',
      setupOnce: 'Сохраните логин и пароль для следующих входов. Эта настройка нужна только один раз.',
      setupHeading: 'Создать аккаунт', setupUsernameHint: 'От 3 символов: латинские буквы, цифры, точка, подчёркивание, @ или дефис.',
      setupPasswordHint: 'Придумайте пароль длиной не меньше 12 символов.', confirmPassword: 'Повторите пароль',
      createAccount: 'Создать аккаунт и войти', creatingAccount: 'Создаём аккаунт…',
      invalid_username: 'Для логина используйте 3–64 латинских буквы, цифры, точку, подчёркивание, @ или дефис.',
      weak_password: 'Придумайте пароль длиной от 12 до 1024 символов.', passwordMismatch: 'Пароли не совпадают. Введите их ещё раз.',
      setup_complete: 'Аккаунт уже создан. Войдите со своим логином и паролем.',
      invalid_setup_token: 'Страница настройки обновилась. Введите пароль ещё раз и повторите.',
      skip: 'К содержимому', uiLanguage: 'Язык интерфейса', viewArticles: 'Статьи на сайте', logout: 'Выйти',
      editorKicker: 'Публикации Dengi Market', pageTitle: 'Редактор статей', connecting: 'Подключаемся к редактору…',
      loginTitle: 'Всё для ваших публикаций', loginIntro: 'Пишите статьи, добавляйте фотографии и публикуйте новости на сайте.',
      signIn: 'Войти', signingIn: 'Входим…', username: 'Логин', password: 'Пароль', firstLogin: 'Первый вход',
      setupHelp: 'Создайте учётную запись администратора в терминале проекта. Команда отдельно запросит пароль.',
      workspace: 'Рабочая область статей', yourArticles: 'Статьи', newArticle: 'Новая статья', editArticle: 'Редактирование статьи',
      findArticle: 'Найти статью', filterStatus: 'Статус', allStatuses: 'Все статусы', draft: 'Черновик', published: 'Опубликовано', archived: 'В архиве', retry: 'Повторить',
      articleFields: 'Содержание статьи', openPublished: 'Открыть на сайте', titleLabel: 'Заголовок', articleLanguage: 'Язык статьи',
      slugLabel: 'Адрес страницы', slugHint: 'Можно оставить пустым — адрес создастся автоматически. Допустимы строчные латинские буквы, цифры и дефисы.',
      excerptLabel: 'Короткий анонс', excerptHint: 'Показывается в списке статей. До 600 символов.', bodyLabel: 'Текст статьи',
      bodyHint: 'Обычный текст. Разделяйте абзацы пустой строкой.', coverTitle: 'Обложка', coverHint: 'Главное изображение статьи и её карточки.',
      chooseCover: 'Загрузить обложку', imagesTitle: 'Фотографии', imagesHint: 'До 12 изображений. Они появятся после текста статьи.', chooseImages: 'Добавить фотографии',
      fileHint: 'PNG, JPEG или WebP. До 8 МБ на изображение.', archiveAction: 'В архив', saveDraft: 'Сохранить черновик', unpublishAction: 'Снять с публикации', publishAction: 'Опубликовать', updatePublication: 'Обновить публикацию',
      discardTitle: 'Сохранить изменения?', discardCopy: 'В статье есть несохранённые изменения. Можно продолжить редактирование или выйти без сохранения.',
      continueEditing: 'Продолжить редактирование', discardAction: 'Не сохранять', signedInAs: 'Вход выполнен',
      loadingList: 'Загружаем статьи…', noArticles: 'Пока нет статей. Начните с новой публикации.', noMatches: 'По этим условиям статьи не найдены.',
      listFailed: 'Не удалось загрузить статьи.', articleCount: 'Статей', unsaved: 'Есть несохранённые изменения.', savedDraft: 'Черновик сохранён.', savedPublished: 'Статья опубликована на сайте.', savedArchived: 'Статья перенесена в архив и больше не видна на сайте.',
      saving: 'Сохраняем…', publishing: 'Публикуем…', unpublishing: 'Снимаем с публикации…', savedUnpublished: 'Статья снята с публикации и сохранена как черновик.', archiving: 'Переносим в архив…', uploading: 'Загружаем изображения…',
      coverAlt: 'Обложка статьи', imageAlt: 'Изображение статьи', remove: 'Удалить', removeCover: 'Удалить обложку', removeImage: 'Удалить изображение',
      titleRequired: 'Перед сохранением укажите заголовок.', bodyRequired: 'Для публикации добавьте текст статьи.', slugInvalid: 'В адресе допустимы строчные латинские буквы, цифры и одиночные дефисы, до 120 символов.',
      imageFormat: 'Выберите изображение PNG, JPEG или WebP.', imageSize: 'Каждое изображение должно быть не больше 8 МБ.', imageCount: 'Можно добавить не больше 12 фотографий.',
      fileRead: 'Не удалось прочитать изображение. Выберите его ещё раз.', imageResponse: 'Сервер вернул некорректный адрес изображения.',
      offline: 'Не удалось подключиться к редактору. Откройте страницу на CMS-сервере: http://127.0.0.1:8345/admin/.',
      invalid_credentials: 'Неверный логин или пароль.', authentication_required: 'Сессия завершилась. Войдите снова — несохранённая статья остаётся здесь.',
      invalid_csrf: 'Сессия обновлена. Повторите действие.', rate_limited: 'Слишком много попыток входа. Подождите минуту и повторите.',
      slug_exists: 'Этот адрес страницы уже занят. Выберите другой.', image_too_large: 'Изображение должно быть не больше 8 МБ.', unsupported_image: 'Допустимы только PNG, JPEG и WebP.',
      mime_mismatch: 'Формат файла не совпадает с содержимым. Сохраните его как PNG, JPEG или WebP.', storage_error: 'Серверу не удалось сохранить данные. Повторите действие.',
      serverRejected: 'Не удалось выполнить действие. Проверьте поля и повторите.', failedResponse: 'Сервер вернул неожиданный ответ.',
      loggedOut: 'Вы вышли из редактора.', setupNeeded: 'Учётная запись администратора ещё не создана. Инструкция для первого входа — ниже.'
    }
  };

  let language = 'en';
  try { language = localStorage.getItem('dengi-ir-language') === 'ru' ? 'ru' : 'en'; } catch { /* The editor also works without storage. */ }
  let session = { authenticated: false, csrf: null, username: null };
  let setupToken = '';
  let articles = [];
  let current = null;
  let cover = '';
  let images = [];
  let dirty = false;
  let busy = false;
  let initialized = false;
  let messageKey = '';
  let messageSuffix = '';
  const uploadPath = /^\/uploads\/[0-9a-f]{32}\.(?:png|jpg|webp)$/;
  const t = key => copy[language][key] || copy.en[key] || key;
  const safeImage = value => typeof value === 'string' && uploadPath.test(value) ? value : '';

  class ApiError extends Error {
    constructor(message, code, status) { super(message); this.code = code; this.status = status; }
  }

  function errorText(error) {
    if (copy[language][error.code]) return t(error.code);
    return language === 'ru' && error.message ? error.message : t('serverRejected');
  }

  async function request(path, { method = 'GET', body, setup = false } = {}) {
    let response;
    try {
      const headers = { Accept: 'application/json' };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      if (method !== 'GET' && session.csrf) headers['X-CSRF-Token'] = session.csrf;
      if (setup && setupToken) headers['X-Setup-Token'] = setupToken;
      response = await fetch(path, { method, headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body) });
    } catch { throw new ApiError(t('offline'), 'offline', 0); }
    let data;
    try { data = await response.json(); } catch { throw new ApiError(t(path === '/api/session' ? 'offline' : 'failedResponse'), path === '/api/session' ? 'offline' : 'failedResponse', response.status); }
    if (!response.ok) throw new ApiError(data.error, data.code || 'serverRejected', response.status);
    return data;
  }

  function notice(key) {
    $('connection-status').textContent = key ? t(key) : '';
    $('connection-status').hidden = !key;
  }

  function message(key, suffix = '') {
    messageKey = key;
    messageSuffix = suffix;
    $('editor-message').textContent = key ? t(key) + suffix : '';
  }

  function clearError(where = 'editor') {
    const node = $(where + '-error');
    node.hidden = true;
    node.textContent = '';
    const form = $(where === 'login' ? 'login-form' : where === 'setup' ? 'setup-form' : 'editor-form');
    form.querySelectorAll('[aria-invalid]').forEach(field => {
      field.removeAttribute('aria-invalid');
      const ids = (field.getAttribute('aria-describedby') || '').split(' ').filter(id => id && id !== where + '-error');
      if (ids.length) field.setAttribute('aria-describedby', ids.join(' '));
      else field.removeAttribute('aria-describedby');
    });
  }

  function showError(text, where = 'editor', field) {
    const node = $(where + '-error');
    node.textContent = text;
    node.hidden = false;
    if (field) {
      field.setAttribute('aria-invalid', 'true');
      const ids = new Set((field.getAttribute('aria-describedby') || '').split(' ').filter(Boolean));
      ids.add(where + '-error');
      field.setAttribute('aria-describedby', [...ids].join(' '));
      field.focus();
    }
    else node.focus();
  }

  function markDirty() {
    dirty = true;
    message('unsaved');
    clearError();
  }

  function updateActions() {
    const status = current?.status || 'draft';
    $('editor-title').textContent = t(current ? 'editArticle' : 'newArticle');
    $('article-status').textContent = t(status);
    $('article-status').className = 'admin-status admin-status-' + status;
    $('save-draft').hidden = false;
    $('save-draft').textContent = t(status === 'published' ? 'unpublishAction' : 'saveDraft');
    $('publish-article').textContent = t(status === 'published' ? 'updatePublication' : 'publishAction');
    $('archive-article').hidden = status === 'archived';
    $('archive-article').disabled = busy || !current;
    $('article-public-link').hidden = status !== 'published';
    if (status === 'published') $('article-public-link').href = '../article/?slug=' + encodeURIComponent(current.slug);
    $('session-label').textContent = session.authenticated ? `${t('signedInAs')}: ${session.username}` : '';
  }

  function setBusy(value) {
    busy = value;
    $('workspace').setAttribute('aria-busy', String(value));
    $('editor-fields').disabled = value;
    $('workspace').querySelectorAll('button, input, select, textarea').forEach(node => { node.disabled = value; });
    $('logout').disabled = value;
    updateActions();
  }

  function translate() {
    document.documentElement.lang = language;
    document.title = 'Dengi Market — ' + t('pageTitle');
    document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = t(node.dataset.i18n); });
    document.querySelectorAll('[data-i18n-label]').forEach(node => { node.setAttribute('aria-label', t(node.dataset.i18nLabel)); });
    document.querySelectorAll('[data-ui-language]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.uiLanguage === language)));
    updateActions();
    renderArticles();
    renderMedia();
    if (messageKey) message(messageKey, messageSuffix);
  }

  function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat(language, { day: 'numeric', month: 'short', year: 'numeric' }).format(date);
  }

  function renderArticles() {
    const search = $('article-search').value.trim().toLocaleLowerCase(language);
    const filter = $('article-filter').value;
    const filtered = articles.filter(article => (filter === 'all' || article.status === filter)
      && (!search || `${article.title} ${article.slug}`.toLocaleLowerCase(language).includes(search)));
    const fragment = document.createDocumentFragment();
    filtered.forEach(article => {
      const li = document.createElement('li');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'admin-article-button';
      button.disabled = busy;
      if (article.id === current?.id) button.setAttribute('aria-current', 'true');
      const title = document.createElement('strong');
      title.textContent = article.title;
      const meta = document.createElement('span');
      meta.className = 'admin-article-meta';
      const badge = document.createElement('span');
      badge.className = 'admin-status admin-status-' + article.status;
      badge.textContent = t(article.status);
      const detail = document.createElement('span');
      detail.textContent = `${article.language.toUpperCase()} · ${formatDate(article.updated_at)}`;
      meta.append(badge, detail);
      button.append(title, meta);
      button.addEventListener('click', async () => { if (!busy && await mayDiscard()) loadArticle(article); });
      li.append(button);
      fragment.append(li);
    });
    $('article-list').replaceChildren(fragment);
    $('library-status').textContent = !articles.length ? t('noArticles') : !filtered.length ? t('noMatches') : `${t('articleCount')}: ${filtered.length}`;
  }

  async function loadArticles() {
    $('library-status').textContent = t('loadingList');
    $('reload-list').hidden = true;
    try {
      const data = await request('/api/admin/articles');
      if (!Array.isArray(data.articles)) throw new ApiError(t('failedResponse'), 'failedResponse');
      articles = data.articles;
      renderArticles();
    } catch (error) {
      $('library-status').textContent = error.status === 401 ? t('authentication_required') : t('listFailed');
      $('reload-list').hidden = false;
      if (error.status === 401) enterLogin('authentication_required');
    }
  }

  function loadArticle(article = null, focus = true) {
    current = article ? { ...article, images: [...article.images] } : null;
    $('editor-form').reset();
    $('article-title').value = article?.title || '';
    $('article-slug').value = article?.slug || '';
    $('article-excerpt').value = article?.excerpt || '';
    $('article-body').value = article?.body || '';
    $('article-language').value = article?.language || language;
    cover = safeImage(article?.cover);
    images = (article?.images || []).map(safeImage).filter(Boolean);
    dirty = false;
    clearError();
    message('');
    updateActions();
    renderMedia();
    renderArticles();
    if (focus) $('article-title').focus();
  }

  function renderMedia() {
    const coverRoot = $('cover-preview');
    coverRoot.replaceChildren();
    if (cover) {
      const figure = document.createElement('figure');
      const image = document.createElement('img');
      image.src = cover;
      image.alt = t('coverAlt');
      image.width = 600;
      image.height = 400;
      image.loading = 'lazy';
      const caption = document.createElement('figcaption');
      const button = document.createElement('button');
      button.className = 'admin-button admin-button-quiet';
      button.type = 'button';
      button.disabled = busy;
      button.textContent = t('removeCover');
      button.addEventListener('click', () => { cover = ''; markDirty(); renderMedia(); $('cover-file').focus(); });
      caption.append(button);
      figure.append(image, caption);
      coverRoot.append(figure);
    }
    const root = $('images-preview');
    root.replaceChildren();
    images.forEach((url, index) => {
      const figure = document.createElement('figure');
      figure.className = 'admin-image-card';
      const image = document.createElement('img');
      image.src = url;
      image.alt = `${t('imageAlt')} ${index + 1}`;
      image.width = 320;
      image.height = 240;
      image.loading = 'lazy';
      const caption = document.createElement('figcaption');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'admin-button admin-button-quiet';
      button.disabled = busy;
      button.textContent = t('remove');
      button.setAttribute('aria-label', `${t('removeImage')} ${index + 1}`);
      button.addEventListener('click', () => { images.splice(index, 1); markDirty(); renderMedia(); $('images-file').focus(); });
      caption.append(button);
      figure.append(image, caption);
      root.append(figure);
    });
  }

  function mayDiscard() {
    if (!dirty) return Promise.resolve(true);
    const dialog = $('discard-dialog');
    return new Promise(resolve => {
      dialog.returnValue = 'cancel';
      dialog.addEventListener('close', () => resolve(dialog.returnValue === 'discard'), { once: true });
      dialog.showModal();
    });
  }

  function enterLogin(key = '') {
    session = { authenticated: false, csrf: null, username: null };
    setupToken = '';
    $('setup-panel').hidden = true;
    $('workspace').hidden = true;
    $('login-panel').hidden = false;
    $('logout').hidden = true;
    $('password').value = '';
    notice(key);
    updateActions();
    if (key === 'authentication_required') $('username').focus();
  }

  async function enterWorkspace(data) {
    session = data;
    setupToken = '';
    $('setup-panel').hidden = true;
    $('login-panel').hidden = true;
    $('workspace').hidden = false;
    $('logout').hidden = false;
    notice('');
    if (!initialized) { loadArticle(null, false); initialized = true; }
    updateActions();
    await loadArticles();
  }

  function enterSetup(data) {
    setupToken = typeof data.setupCsrf === 'string' ? data.setupCsrf : '';
    session = { authenticated: false, csrf: null, username: null };
    $('setup-panel').hidden = false;
    $('login-panel').hidden = true;
    $('workspace').hidden = true;
    $('logout').hidden = true;
    notice('');
    updateActions();
  }

  async function handleEditorError(error) {
    if (error.status === 401) { enterLogin('authentication_required'); return; }
    if (error.code === 'invalid_csrf') {
      try {
        const data = await request('/api/session');
        if (!data.authenticated) { enterLogin('authentication_required'); return; }
        session = data;
      } catch { /* The original failed action remains visible and can be retried. */ }
    }
    showError(errorText(error));
  }

  async function saveArticle(status) {
    if (busy) return;
    clearError();
    const payload = {
      title: $('article-title').value.trim(), excerpt: $('article-excerpt').value.trim(), body: $('article-body').value.trim(),
      slug: $('article-slug').value.trim(), language: $('article-language').value, status, cover, images: [...images]
    };
    if (!payload.title) { showError(t('titleRequired'), 'editor', $('article-title')); return; }
    if (payload.slug && (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(payload.slug) || payload.slug.length > 120)) { showError(t('slugInvalid'), 'editor', $('article-slug')); return; }
    if (status === 'published' && !payload.body) { showError(t('bodyRequired'), 'editor', $('article-body')); return; }
    const unpublishing = current?.status === 'published' && status === 'draft';
    setBusy(true);
    message(status === 'published' ? 'publishing' : status === 'archived' ? 'archiving' : unpublishing ? 'unpublishing' : 'saving');
    try {
      const data = await request('/api/admin/articles' + (current ? '/' + current.id : ''), { method: current ? 'PUT' : 'POST', body: payload });
      if (!data.article?.id) throw new ApiError(t('failedResponse'), 'failedResponse');
      articles = [data.article, ...articles.filter(article => article.id !== data.article.id)];
      loadArticle(data.article, false);
      message(status === 'published' ? 'savedPublished' : status === 'archived' ? 'savedArchived' : unpublishing ? 'savedUnpublished' : 'savedDraft');
    } catch (error) { message(dirty ? 'unsaved' : ''); await handleEditorError(error); }
    finally { setBusy(false); }
  }

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1]);
      reader.onerror = () => reject(new ApiError(t('fileRead'), 'fileRead'));
      reader.onabort = reader.onerror;
      reader.readAsDataURL(file);
    });
  }

  async function uploadFiles(input, isCover) {
    const files = [...input.files];
    input.value = '';
    if (!files.length || busy) return;
    clearError();
    if (!isCover && images.length + files.length > 12) { showError(t('imageCount')); return; }
    for (const file of files) {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { showError(t('imageFormat')); return; }
      if (file.size > 8 * 1024 * 1024) { showError(t('imageSize')); return; }
    }
    setBusy(true);
    try {
      for (let index = 0; index < files.length; index++) {
        const file = files[index];
        message('uploading', ` (${index + 1}/${files.length})`);
        const data = await request('/api/uploads', { method: 'POST', body: { filename: file.name, mime: file.type, data: await readFile(file) } });
        if (!safeImage(data.url)) throw new ApiError(t('imageResponse'), 'imageResponse');
        if (isCover) cover = data.url;
        else images.push(data.url);
        dirty = true;
        renderMedia();
      }
      message('unsaved');
    } catch (error) { message(dirty ? 'unsaved' : ''); await handleEditorError(error); }
    finally { setBusy(false); }
  }

  document.querySelectorAll('[data-ui-language]').forEach(button => button.addEventListener('click', () => {
    language = button.dataset.uiLanguage;
    try { localStorage.setItem('dengi-ir-language', language); } catch { /* Optional interface preference. */ }
    translate();
  }));
  $('setup-form').addEventListener('submit', async event => {
    event.preventDefault();
    if ($('setup-submit').disabled) return;
    clearError('setup');
    const username = $('setup-username').value.trim();
    const password = $('setup-password').value;
    if (!/^[A-Za-z0-9_.@-]{3,64}$/.test(username)) { showError(t('invalid_username'), 'setup', $('setup-username')); return; }
    if (password.length < 12 || password.length > 1024) { showError(t('weak_password'), 'setup', $('setup-password')); return; }
    if (password !== $('setup-confirm').value) { showError(t('passwordMismatch'), 'setup', $('setup-confirm')); return; }
    if (!setupToken) { showError(t('offline'), 'setup'); return; }
    const controls = [...$('setup-form').querySelectorAll('input, button')];
    controls.forEach(field => { field.disabled = true; });
    $('setup-submit').textContent = t('creatingAccount');
    $('setup-form').setAttribute('aria-busy', 'true');
    try {
      const data = await request('/api/setup', { method: 'POST', body: { username, password }, setup: true });
      $('username').value = username;
      await enterWorkspace(data);
      if (session.authenticated) $('article-title').focus();
    } catch (error) {
      if (error.code === 'invalid_setup_token' || error.code === 'setup_complete') {
        try {
          const data = await request('/api/session');
          if (data.authenticated) { await enterWorkspace(data); return; }
          if (data.adminConfigured) { $('username').value = username; enterLogin('setup_complete'); return; }
          enterSetup(data);
        } catch { /* Keep the failed action visible so the user can retry. */ }
      }
      showError(errorText(error), 'setup');
    } finally {
      $('setup-password').value = '';
      $('setup-confirm').value = '';
      controls.forEach(field => { field.disabled = false; });
      $('setup-submit').textContent = t('createAccount');
      $('setup-form').setAttribute('aria-busy', 'false');
    }
  });
  $('login-form').addEventListener('submit', async event => {
    event.preventDefault();
    clearError('login');
    const username = $('username').value.trim();
    const password = $('password').value;
    if (!username || !password) return;
    $('login-submit').disabled = true;
    $('login-submit').textContent = t('signingIn');
    $('login-form').setAttribute('aria-busy', 'true');
    try {
      const data = await request('/api/login', { method: 'POST', body: { username, password } });
      $('password').value = '';
      await enterWorkspace(data);
      if (session.authenticated) $('article-title').focus();
    } catch (error) { showError(errorText(error), 'login'); }
    finally { $('password').value = ''; $('login-submit').disabled = false; $('login-submit').textContent = t('signIn'); $('login-form').setAttribute('aria-busy', 'false'); }
  });
  $('logout').addEventListener('click', async () => {
    if (busy || !await mayDiscard()) return;
    setBusy(true);
    try {
      await request('/api/logout', { method: 'POST', body: {} });
      loadArticle(null, false);
      initialized = false;
      articles = [];
      enterLogin('loggedOut');
      $('username').focus();
    } catch (error) { await handleEditorError(error); }
    finally { setBusy(false); }
  });
  $('new-article').addEventListener('click', async () => { if (!busy && await mayDiscard()) loadArticle(); });
  $('reload-list').addEventListener('click', loadArticles);
  $('article-search').addEventListener('input', renderArticles);
  $('article-filter').addEventListener('change', renderArticles);
  $('editor-fields').addEventListener('input', event => { if (event.target.type !== 'file') markDirty(); });
  $('editor-fields').addEventListener('change', event => { if (event.target.tagName === 'SELECT') markDirty(); });
  $('editor-form').addEventListener('submit', event => { event.preventDefault(); saveArticle(event.submitter?.dataset.status || (current?.status === 'published' ? 'published' : 'draft')); });
  $('editor-form').addEventListener('keydown', event => { if (event.key === 'Enter' && event.target.tagName === 'INPUT') event.preventDefault(); });
  $('archive-article').addEventListener('click', () => { if (current) saveArticle('archived'); });
  $('cover-file').addEventListener('change', () => uploadFiles($('cover-file'), true));
  $('images-file').addEventListener('change', () => uploadFiles($('images-file'), false));
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });

  translate();
  request('/api/session').then(async data => {
    if (data.authenticated) await enterWorkspace(data);
    else if (data.adminConfigured === false) enterSetup(data);
    else {
      enterLogin();
    }
  }).catch(error => {
    enterLogin('');
    $('connection-status').textContent = errorText(error);
    $('connection-status').hidden = false;
  });
})();
