'use strict';
// Pacific Drive save editor — front end. Game data (names, icons, layouts, presets, settings menu,
// research graph) comes from /api/gamedata, the save state from /api/*.

const $ = (s, el = document) => el.querySelector(s);
const h = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === 'class') e.className = v;
    else if (k === 'style') e.style.cssText = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k.nodeType ? k : String(k));
  return e;
};

// ------------------------------------------------------------------ UI strings
const UI = {
  ru: {
    editor: '// РЕДАКТОР СОХРАНЕНИЙ', folder: 'Папка…', quit: 'Выход', bye: 'Редактор остановлен. Вкладку можно закрыть.',
    setup_title: 'Первый запуск', setup_text: 'Редактору нужны названия, иконки и раскладки из вашей копии игры. Они извлекаются из .pak-файлов один раз и хранятся только у вас — в сборке редактора их нет.',
    setup_found: 'Найденные установки Pacific Drive', setup_none: 'Игра не найдена автоматически — укажите папку вручную.',
    setup_custom: 'Папка игры (где лежит PenDriverPro):', setup_go: 'Извлечь данные', setup_running: 'Извлечение… (около 10–30 секунд)',
    setup_done: 'Готово! Загружаю редактор…', setup_where: 'Данные будут сохранены в:', redo_setup: 'Извлечь данные игры заново', revert: 'Отменить изменения', save: 'Сохранить',
    tab_inventory: 'Инвентарь', tab_car: 'Автомобиль', tab_research: 'Исследования', tab_economy: 'Энергия и ресурсы',
    tab_settings: 'Настройки игры', tab_summary: 'Сводка', containers: 'Контейнеры',
    grid_hint: 'Выберите предмет в каталоге → наведите на сетку → клик, чтобы положить. R — повернуть, Esc — отмена. Предмет можно перетащить; Delete — удалить выбранный.',
    list_hint: 'Хранилище со стопками: задайте общее количество — редактор сам разложит предметы. Новый тип — клик по предмету в каталоге.',
    named_hint: 'Стеллаж: у каждого места своя ячейка. Выберите место, затем предмет в каталоге.',
    car_hint: 'Детали по местам установки. Выберите место, чтобы заменить деталь, починить её, перекрасить или снять эффекты.',
    research_hint: 'Дерево исследований из игры. Колёсико — масштаб, перетаскивание — прокрутка, клик по узлу — подробности.',
    currencies: 'Энергия якорей и опыт', resources: 'Состояние машины и игрока',
    catalog: 'Каталог предметов', search: 'Поиск по названию…', all: 'Все', count: 'Количество', max: 'Макс.',
    rotate: 'Повернуть', del: 'Удалить', size: 'Размер', stack: 'Стопка до', category: 'Категория',
    allow_over: 'разрешить больше стопки', no_save: 'Сохранение не открыто. Выберите файл вверху.', saved: 'Сохранено. Резервная копия: ',
    unsaved: 'Есть несохранённые изменения', confirm_revert: 'Отменить все несохранённые изменения?',
    dir_prompt: 'Папка с сохранениями (SaveGames):', empty_storage: 'Хранилище пусто', empty: 'Пусто',
    total: 'Всего', stacks: 'стопок', add_stack: '+ стопка', reset: 'Сбросить к значению пресета',
    on: 'ВКЛ', off: 'ВЫКЛ', preset_note: 'Изменённые настройки хранятся поверх выбранного пресета (как в меню игры).',
    placing: 'Размещение: ', stacked: 'Добавлено', last_played: 'Последняя игра', playtime: 'Время в игре', level: 'Уровень',
    runs: 'Вылазок', miles: 'Пройдено миль', mission: 'Текущее задание', build: 'Версия игры', file: 'Файл', h: 'ч', m: 'мин',
    res_PlayerHealth: 'Здоровье игрока', res_CarHealth: 'Прочность машины', res_CarLim: 'Заряд аккумулятора (кЛИМ)',
    res_Fuel: 'Топливо', res_Shield: 'Щит', res_more: 'Прочие параметры', mechxp: 'Опыт механика',
    cat_resources: 'Ресурсы', cat_tools: 'Инструменты', cat_essentials: 'Важное', cat_car: 'Детали машины',
    cat_equip: 'Снаряжение', cat_cosmetics: 'Украшения', cat_garage: 'Гараж', cat_collect: 'Коллекция', cat_other: 'Прочее',
    g_player: 'Игрок и багажник', g_car: 'На машине', g_storage: 'Хранилища гаража', g_parts: 'Стеллажи деталей',
    g_tubes: 'Пневмопочта', g_garage: 'Станции гаража', g_mounts: 'Настенные рамки',
    paint: 'Краска', decal: 'Декаль', none: '— нет —', toolbox: 'Ящик с инструментами', frame: 'Рамка',
    f_Durability: 'Прочность', f_Health: 'Состояние', f_Fatigue: 'Износ', f_Fuel: 'Топливо', f_BATTERY: 'Заряд',
    f_Battery: 'Заряд', f_CurrentCharge: 'Заряд станции', f_LockStrength: 'Замок',
    no_effects: 'Игра не допускает новых эффектов для этого предмета (или лимит исчерпан).',
    repair: 'Починить', repair_all: 'Починить всё', effects: 'Эффекты', add_effect: '+ эффект…', hidden_eff: 'служебный',
    item_n: 'Предмет', not_stored: 'по умолчанию', part: 'Деталь', compatible: 'Подходящие детали', remove: 'Убрать',
    s_locked: 'Закрыто', s_available: 'Доступно', s_researched: 'Исследовано', s_installed: 'Установлено',
    research_cost: 'Стоимость исследования', craft_cost: 'Стоимость изготовления', conditions: 'Условия',
    installed_q: 'Улучшение установлено в гараже', install_note: 'Исследованное улучшение можно не устанавливать — как в игре, где его ещё нужно построить.',
    layout_note: 'Изменение вместимости хранилища вступит в силу, когда игра применит улучшение.',
    tubes_in: 'Пневмопочта: входящие', tubes_out: 'Пневмопочта: исходящие', transfer: 'Перенос в гараж',
    racks_parts: 'Стеллаж деталей', transfer_tray: 'лоток', unique: 'Уникальные предметы', paint_shelf: 'Полка с красками',
    car_body: 'Кузов', car_ess: 'Двигатель и колёса', car_att: 'Навесное оборудование', car_int: 'Салон и приборы',
    car_cos: 'Украшения', car_perf: 'Ходовая', car_other: 'Прочее',
    tab_codex: 'Журнал', c_all: 'Все', c_open: 'Открытые', c_closed: 'Закрытые', open_all: 'Открыть все', close_all: 'Закрыть все',
    c_opened: 'Открыто', c_read: 'Прочитано', c_date: 'Дата записи', c_needed: 'Нужно для исследований', c_locked: 'Запись закрыта',
    c_photo: 'есть снимок', c_confirm_close: 'Закрыть все записи этого раздела?',
    why: 'Почему недоступно', parents: 'Предыдущие узлы', by_default: 'Открыт с начала игры', cond_ok: 'выполнено',
    cond_no: 'не выполнено', open_entry: 'Открыть запись журнала', cond_manual: 'проверяется игрой (по состоянию мира)',
    parent_needed: 'нужно исследовать хотя бы один из предыдущих', make_available: 'Сделать доступным',
    tab_stats: 'Статистика', stats_hint: 'Статистика из прогресса игры (её показывают табло в гараже и экран итогов). Число заездов и пробег также обновляются в превью сохранения.',
    wb_all: 'Все значения прогресса (для опытных)', wb_warn: 'Это внутреннее состояние игры: задания, сканирования, маршруты, мир. Неверные значения могут сломать сюжет — меняйте осознанно, резервная копия создаётся при сохранении.',
    wb_add: 'Добавить тег', wb_tag: 'тег', wb_value: 'значение', st_runs: 'Заезды', st_car: 'Автомобиль', st_player: 'Игрок',
    st_res: 'Ресурсы и энергия', st_anom: 'Аномалии и состояния', st_quirks: 'Парадоксы', st_other: 'Прочее',
    r_all: 'Все заезды', r_crit: 'Сюжетные', r_supply: 'За припасами', r_exp: 'Экспедиции',
    c_total: 'Всего', c_succ: 'Успешно', c_fail: 'Провалено', c_sstreak: 'Серия успехов', c_fstreak: 'Серия провалов',
    q_invocations: 'срабатываний', q_diag: 'Диагностирован', q_undiag: 'Не диагностирован', q_diagnose: 'Диагностировать',
    q_fix: 'Исправить', q_cure: 'Для починки', q_add: 'Добавить парадокс', q_when: 'Когда', q_what: 'Что происходит',
    q_add_btn: '+ Добавить', q_add_diag: 'сразу диагностирован', q_grave: 'Исправленные ранее', q_revivals: 'возвратов',
    q_flags: 'Подсказки', q_banned: 'игра не сочетает это поведение с таким условием', q_none: 'Парадоксов нет',
    f_ShowIncorrectQuirkGuess: 'Показывать неверные догадки', f_AllowGuessHints: 'Подсказки при угадывании', f_AllowSolutionHints: 'Подсказки решения',
  },
  en: {
    editor: '// SAVE EDITOR', folder: 'Folder…', quit: 'Exit', bye: 'The editor has stopped. You can close this tab.',
    setup_title: 'First start', setup_text: 'The editor needs names, icons and layouts from your copy of the game. They are extracted from the .pak files once and stay on your computer — the editor download does not include them.',
    setup_found: 'Detected Pacific Drive installations', setup_none: 'The game was not found automatically — enter its folder.',
    setup_custom: 'Game folder (the one containing PenDriverPro):', setup_go: 'Extract game data', setup_running: 'Extracting… (about 10–30 seconds)',
    setup_done: 'Done! Loading the editor…', setup_where: 'Data will be stored in:', redo_setup: 'Re-extract game data', revert: 'Revert changes', save: 'Save',
    tab_inventory: 'Inventory', tab_car: 'Car', tab_research: 'Research', tab_economy: 'Energy & resources',
    tab_settings: 'Gameplay settings', tab_summary: 'Summary', containers: 'Containers',
    grid_hint: 'Pick an item in the catalog → hover the grid → click to drop. R rotates, Esc cancels. Drag to move; Delete removes the selected one.',
    list_hint: 'Stacked storage: set the total and the editor splits it into stacks. New type: click an item in the catalog.',
    named_hint: 'Rack: every place has its own cell. Pick a place, then an item in the catalog.',
    car_hint: 'Parts by mounting point. Pick a point to swap, repair, repaint the part or remove effects.',
    research_hint: 'The game research tree. Wheel zooms, drag pans, click a node for details.',
    currencies: 'Anchor energy & XP', resources: 'Car & player state',
    catalog: 'Item catalog', search: 'Search by name…', all: 'All', count: 'Count', max: 'Max',
    rotate: 'Rotate', del: 'Delete', size: 'Size', stack: 'Stacks to', category: 'Category',
    allow_over: 'allow over-stacking', no_save: 'No save open. Pick a file at the top.', saved: 'Saved. Backup: ',
    unsaved: 'You have unsaved changes', confirm_revert: 'Discard all unsaved changes?',
    dir_prompt: 'Save folder (SaveGames):', empty_storage: 'Storage is empty', empty: 'Empty',
    total: 'Total', stacks: 'stacks', add_stack: '+ stack', reset: 'Reset to preset value',
    on: 'ON', off: 'OFF', preset_note: 'Changed settings are stored on top of the selected preset (like the game menu).',
    placing: 'Placing: ', stacked: 'Added', last_played: 'Last played', playtime: 'Play time', level: 'Level',
    runs: 'Runs', miles: 'Miles driven', mission: 'Current mission', build: 'Game build', file: 'File', h: 'h', m: 'min',
    res_PlayerHealth: 'Player health', res_CarHealth: 'Car health', res_CarLim: 'Battery charge (kLIM)',
    res_Fuel: 'Fuel', res_Shield: 'Shield', res_more: 'Other values', mechxp: 'Mechanic XP',
    cat_resources: 'Resources', cat_tools: 'Tools', cat_essentials: 'Essentials', cat_car: 'Car parts',
    cat_equip: 'Equipment', cat_cosmetics: 'Cosmetics', cat_garage: 'Garage', cat_collect: 'Collectibles', cat_other: 'Other',
    g_player: 'Player & trunk', g_car: 'On the car', g_storage: 'Garage storage', g_parts: 'Part racks',
    g_tubes: 'Pneumatic tubes', g_garage: 'Garage stations', g_mounts: 'Wall frames',
    paint: 'Paint', decal: 'Decal', none: '— none —', toolbox: 'Toolbox', frame: 'Frame',
    f_Durability: 'Durability', f_Health: 'Condition', f_Fatigue: 'Wear', f_Fuel: 'Fuel', f_BATTERY: 'Charge',
    f_Battery: 'Charge', f_CurrentCharge: 'Station charge', f_LockStrength: 'Lock',
    no_effects: 'The game allows no further effects on this item (or the limit is reached).',
    repair: 'Repair', repair_all: 'Repair all', effects: 'Effects', add_effect: '+ effect…', hidden_eff: 'internal',
    item_n: 'Item', not_stored: 'default', part: 'Part', compatible: 'Compatible parts', remove: 'Remove',
    s_locked: 'Locked', s_available: 'Available', s_researched: 'Researched', s_installed: 'Installed',
    research_cost: 'Research cost', craft_cost: 'Crafting cost', conditions: 'Conditions',
    installed_q: 'Upgrade installed in the garage', install_note: 'A researched upgrade may stay uninstalled — in game it still has to be built.',
    layout_note: 'Storage capacity changes once the game applies the upgrade.',
    tubes_in: 'Tubes: incoming', tubes_out: 'Tubes: outgoing', transfer: 'Garage transfer',
    racks_parts: 'Part rack', transfer_tray: 'tray', unique: 'Unique items', paint_shelf: 'Paint shelf',
    car_body: 'Body', car_ess: 'Engine & wheels', car_att: 'Attachments', car_int: 'Interior & gauges',
    car_cos: 'Cosmetics', car_perf: 'Chassis', car_other: 'Other',
    tab_codex: 'Logbook', c_all: 'All', c_open: 'Unlocked', c_closed: 'Locked', open_all: 'Unlock all', close_all: 'Lock all',
    c_opened: 'Unlocked', c_read: 'Read', c_date: 'Logged on', c_needed: 'Needed for research', c_locked: 'Entry locked',
    c_photo: 'has a photo', c_confirm_close: 'Lock every entry in this section?',
    why: 'Why it is unavailable', parents: 'Previous nodes', by_default: 'Unlocked from the start', cond_ok: 'done',
    cond_no: 'not done', open_entry: 'Unlock logbook entry', cond_manual: 'checked by the game (world state)',
    parent_needed: 'research at least one previous node', make_available: 'Make available',
    tab_stats: 'Statistics', stats_hint: 'Statistics from the game progress (shown by the garage status board and run results). Run count and mileage are also updated in the save preview.',
    wb_all: 'All progress values (advanced)', wb_warn: 'This is internal game state: missions, scans, routes, world. Wrong values can break the story — edit deliberately; a backup is made on save.',
    wb_add: 'Add tag', wb_tag: 'tag', wb_value: 'value', st_runs: 'Runs', st_car: 'Car', st_player: 'Player',
    st_res: 'Resources & energy', st_anom: 'Anomalies & statuses', st_quirks: 'Quirks', st_other: 'Other',
    r_all: 'All runs', r_crit: 'Story', r_supply: 'Supply', r_exp: 'Expeditions',
    c_total: 'Total', c_succ: 'Successful', c_fail: 'Failed', c_sstreak: 'Success streak', c_fstreak: 'Failure streak',
    q_invocations: 'triggers', q_diag: 'Diagnosed', q_undiag: 'Not diagnosed', q_diagnose: 'Diagnose',
    q_fix: 'Fix', q_cure: 'Fix needs', q_add: 'Add a quirk', q_when: 'When', q_what: 'What happens',
    q_add_btn: '+ Add', q_add_diag: 'already diagnosed', q_grave: 'Fixed before', q_revivals: 'revivals',
    q_flags: 'Hints', q_banned: 'the game never pairs this behavior with this condition', q_none: 'No quirks',
    f_ShowIncorrectQuirkGuess: 'Show incorrect guesses', f_AllowGuessHints: 'Guess hints', f_AllowSolutionHints: 'Solution hints',
  },
};
UI.uk = UI.ru;
const LANG_NAMES = { en: 'English', ru: 'Русский', uk: 'Українська', de: 'Deutsch', fr: 'Français', es: 'Español',
  it: 'Italiano', pl: 'Polski', 'pt-BR': 'Português (BR)', tr: 'Türkçe', ja: '日本語', ko: '한국어', 'zh-CN': '简体中文', 'zh-TW': '繁體中文' };

// Values the game uses when a preset does not override them (from a real save's UserSettings).
const DEFAULTS = {
  bEnableEmergencyGasCan: 'true', bKeepCraftedItemsOnDeath: 'false', HardcoreMode: '1', AbandonRunConsequences: '1',
  AbandonSaveQuitConsequences: '1', DrivingAssistFactor: '0', Difficulty: '1', bEnableHazards: 'true', QuirkFrequency: '2',
  bQuirkConsistency: 'false', bFreeQuirkHints: 'false', bFreeQuirkGuesses: 'false', bBlockHarmfulStatusEffects: 'false',
  bEnableDamage: 'true', bEnablePlayerDamage: 'true', bEnableAmbientDamage: 'true', bEnableInfiniteGas: 'false',
  PauseWhileInMenus: '0', bInvulnerableToAmbientDamageWhileInMenus: 'false', bRetainFuelCan: 'true',
  CraftingRecipeMultiplier: '1', bEnableEasyIgnition: 'true', bEnableEasyPartSwap: 'true', bEnableEasyShifter: 'false',
  bHeadlightsWorkWithoutBattery: 'false', bEnableWindshieldSplash: 'true', bRainAffectsDriving: 'true', CarProtectionMode: '0',
  bAutoFillResourcesOnReturn: 'false', bFreeRepairOnSuccessfulReturn: 'false', bDisableInstabilityStorms: 'false',
  bDisableGatewayStorms: 'false', bEnablePlayerDeath: 'true', bTODFasterNights: 'false',
};
const PRESET_ORDER = ['easy1', 'easy2', 'standard', 'hard1', 'hard2', 'hard3', 'ironcar'];
const CATS = [
  ['resources', c => ['Resources', 'Refined'].includes(c), '#5a4a35'],
  ['tools', c => c === 'Tools', '#34475a'],
  ['essentials', c => ['Essentials', 'Maintenance'].includes(c), '#4b5a34'],
  ['car', c => c.startsWith('Attach'), '#4d4f45'],
  ['equip', c => c === 'PlayerEquipment', '#3d5548'],
  ['cosmetics', c => c === 'Cosmetics', '#4f3c58'],
  ['garage', c => c === 'GarageCosmetics', '#58463c'],
  ['collect', c => c === 'Collectible', '#2f5655'],
  ['other', c => true, '#3b463f'],
];
const HIDDEN_ITEM = /Template|_Empty|EmptyItem|DEBUG|_Test|Test_|_OLD|GameplayEventItem|Garage_SpawnModifier/;
const ALERT_COLORS = { Dangerous: [0.85, 0.3, 0.22], Warning: [0.94, 0.62, 0.2], Harmless: [0.85, 0.85, 0.8], Invisible: [0.5, 0.5, 0.5] };

// ------------------------------------------------------------------ state
let GD = null, ST = null;
let lang = localStorage.getItem('pd_lang') || (navigator.language || 'ru').slice(0, 2);
let curCont = null, selSlot = null, slotInst = null;
let placing = null;
let catFilter = 'all', catSearch = '', overStack = false;
let carSel = null, nodeSel = null;
let view = { x: 0, y: 0, z: 0.35, init: false };
let mouse = { x: 0, y: 0 };

const t = k => (UI[lang] || UI.en)[k] || UI.en[k] || k;
const L = obj => (obj && (obj[lang] || obj.en || Object.values(obj)[0])) || '';
const item = a => (a && GD.items[a]) || { id: (a || '?').split('.').pop(), name: {}, desc: {}, size: [2, 2], stack: 1, category: '' };
const itemName = a => L(item(a).name) || item(a).id;
const catOf = c => CATS.find(([, f]) => f(c || ''));
const tileColor = a => catOf(item(a).category)[2];
const fmt = v => (v === null || v === undefined) ? '—' : (Math.abs(v - Math.round(v)) < 1e-6 ? String(Math.round(v)) : v.toFixed(1));

function icon(src, tint, cls = '') {
  if (!src) return h('div', { class: 'noicon ' + cls }, '?');
  if (tint) {
    const [r, g, b] = tint.map(v => Math.round(Math.min(1, v) * 255));
    return h('div', { class: 'tinted ' + cls, style: `background:rgb(${r},${g},${b});` +
      `-webkit-mask:url(/gamedata/${src}) center/contain no-repeat;mask:url(/gamedata/${src}) center/contain no-repeat` });
  }
  return h('img', { src: '/gamedata/' + src, class: cls, loading: 'lazy', alt: '' });
}
const itemIcon = a => icon(item(a).icon, item(a).tint);

// ------------------------------------------------------------------ api
async function api(op, args = {}) {
  $('#busy').classList.remove('hidden');
  try {
    const r = await fetch('/api/' + op, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args) });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.statusText);
    if (j && j.containers) { ST = j; await refreshSlotInst(); render(); }
    return j;
  } catch (e) {
    toast(e.message, true);
    throw e;
  } finally {
    $('#busy').classList.add('hidden');
  }
}
const quiet = p => p.catch(() => {});

function toast(msg, err = false) {
  const el = $('#toast');
  el.textContent = msg;
  el.className = 'toast' + (err ? ' err' : '');
  clearTimeout(toast.tm);
  toast.tm = setTimeout(() => el.classList.add('hidden'), err ? 6000 : 3500);
}

// ------------------------------------------------------------------ boot
async function boot() {
  GD = await (await fetch('/api/gamedata')).json();
  $('#btnQuit').onclick = async () => {
    if (ST && ST.dirty && !confirm(t('confirm_revert'))) return;
    try { await fetch('/api/quit', { method: 'POST', body: '{}' }); } catch (e) { /* server gone */ }
    document.body.innerHTML = '';
    document.body.append(h('div', { class: 'empty', style: 'margin-top:20vh;font-size:18px' }, t('bye')));
  };
  if (GD.missing) { applyStatic(); return showSetup(); }
  document.title = `Pacific Drive — ${t('editor').replace('// ', '')} ${GD.version || ''}`;
  if (!GD.langs.includes(lang) && !UI[lang]) lang = 'en';
  const ls = $('#langSelect');
  for (const l of GD.langs) ls.append(h('option', { value: l, selected: l === lang }, LANG_NAMES[l] || l));
  ls.onchange = () => { lang = ls.value; localStorage.setItem('pd_lang', lang); applyStatic(); render(); };
  applyStatic();
  for (const b of document.querySelectorAll('#tabs button')) b.onclick = () => switchTab(b.dataset.tab);
  $('#btnSave').onclick = async () => { const r = await api('save'); toast(t('saved') + (r.backup || '—')); };
  $('#btnReload').onclick = () => { if (confirm(t('confirm_revert'))) quiet(api('reload')); };
  $('#btnRepairCar').onclick = () => quiet(api('carrepair'));
  $('#btnDir').onclick = async () => {
    const d = prompt(t('dir_prompt'), (await (await fetch('/api/saves')).json()).dirs[0] || '');
    if (d) { await api('setdir', { dir: d }); loadSaves(); }
  };
  $('#saveSelect').onchange = e => { if (!ST || !ST.dirty || confirm(t('confirm_revert'))) quiet(api('open', { path: e.target.value })); };
  window.addEventListener('beforeunload', e => { if (ST && ST.dirty) { e.preventDefault(); e.returnValue = ''; } });
  document.addEventListener('keydown', onKey);
  document.addEventListener('mousemove', e => { mouse = { x: e.clientX, y: e.clientY }; if (placing) updateGhost(); });
  setupResearchCanvas();
  await loadSaves();
  try { const r = await fetch('/api/state', { method: 'POST', body: '{}' }); if (r.ok) ST = await r.json(); } catch (e) { /* no save yet */ }
  render();
}

async function loadSaves() {
  const j = await (await fetch('/api/saves')).json();
  const sel = $('#saveSelect');
  sel.innerHTML = '';
  sel.append(h('option', { value: '' }, j.saves.length ? '— odsave… —' : '— no saves found —'));
  for (const s of j.saves)
    sel.append(h('option', { value: s.path, selected: ST && ST.path === s.path }, `${s.name}  ·  ${new Date(s.mtime * 1000).toLocaleString()}`));
}

function applyStatic() {
  document.documentElement.lang = lang;
  for (const el of document.querySelectorAll('[data-t]')) el.textContent = t(el.dataset.t);
}

function switchTab(name) {
  for (const b of document.querySelectorAll('#tabs button')) b.classList.toggle('active', b.dataset.tab === name);
  for (const s of document.querySelectorAll('.tab')) s.classList.toggle('active', s.id === 'tab-' + name);
  cancelPlacing();
  if (name === 'research') renderResearch();
}

function render() {
  $('#btnSave').classList.toggle('dirty', !!(ST && ST.dirty));
  $('#btnSave').title = ST && ST.dirty ? t('unsaved') : '';
  if (!ST) {
    $('#contView').innerHTML = '';
    $('#contView').append(h('div', { class: 'empty' }, t('no_save')));
    return;
  }
  renderContainers(); renderContView(); renderDetails();
  renderCatalog($('#catalogPanel'));
  renderCar(); renderEconomy(); renderSettings(); renderSummary(); renderCodex(); renderStats();
  if ($('#tab-research').classList.contains('active')) renderResearch();
}

// ------------------------------------------------------------------ containers
const conts = () => ST.allContainers || [];
const cont = () => conts().find(c => c.guid === curCont);

function contLabel(c) {
  const id = c.layout || '', st = c.station || '';
  if (c.key === 'Inventory_Trunk') return L(GD.strings.container_trunk) || 'Trunk';
  if (c.key === 'Inventory_Player') return L(GD.strings.container_pack) || 'Pack';
  if (c.key === 'Inventory_Tubes_In') return t('tubes_in');
  if (c.key === 'Inventory_Tubes_Out') return t('tubes_out');
  if (c.key === 'Inventory_GarageTransfer') return t('transfer');
  if (c.key === 'Inventory_Paint') return t('paint_shelf');
  if (c.key === 'Inventory_UniqueItems') return t('unique');
  if (c.group === 'parts') return `${t('racks_parts')} · ${st.split('.').pop()}${c.kind === 'grid' ? ' · ' + t('transfer_tray') : ''}`;
  if (st.includes('Mount.')) return t('frame') + ' ' + st.split('.').pop();
  if (c.group === 'storage') return `${L(GD.strings.container_storage) || 'Storage'} · ${st.split('.').pop()}`;
  if (c.owner) return itemName(Object.keys(GD.items).find(a => GD.items[a].id === c.owner)) || c.owner;
  if (id === 'CL_Lootable_Toolbox') return t('toolbox');
  return (c.key || id).replace(/^Inventor(y|ies)_/, '').replace(/^CL_/, '');
}
const contCount = c => c.kind === 'list' ? Object.values(c.totals).reduce((a, b) => a + b, 0)
  : (c.slots || []).reduce((s, x) => s + (x.count || 0), 0);

function renderContainers() {
  const box = $('#containerList');
  box.innerHTML = '';
  const cs = conts();
  if (!curCont || !cont()) curCont = (cs.find(c => c.key === 'Inventory_Trunk') || cs[0] || {}).guid;
  let group = null, holder = box;
  for (const c of cs) {
    if (c.group !== group) {
      group = c.group;
      const d = h('details', { open: group !== 'mounts' || cs.some(x => x.group === 'mounts' && x.guid === curCont) },
        h('summary', {}, t('g_' + group)));
      box.append(d);
      holder = d;
    }
    holder.append(h('button', { class: 'cont-btn' + (c.guid === curCont ? ' active' : ''),
      onclick: () => { curCont = c.guid; selSlot = null; slotInst = null; cancelPlacing(); render(); } },
      contLabel(c), h('small', {}, contCount(c))));
  }
}

function renderContView() {
  const c = cont(), box = $('#contView');
  box.innerHTML = '';
  if (!c) return;
  const extra = c.kind === 'grid' ? `  ${c.w}×${c.h}` : '';
  $('#gridTitle').textContent = contLabel(c) + extra;
  $('#gridHint').textContent = t(c.kind + '_hint');
  if (c.kind === 'grid') renderGrid(c, box);
  else if (c.kind === 'list') renderList(c, box);
  else renderNamed(c, box);
}

const cellPx = () => parseInt(getComputedStyle(document.documentElement).getPropertyValue('--cell')) || 44;

function renderGrid(c, box) {
  const wrap = h('div', { class: 'grid-wrap' }), grid = h('div', { class: 'grid', id: 'grid' });
  wrap.append(grid); box.append(wrap);
  const cp = cellPx();
  grid.style.width = c.w * cp + 'px';
  grid.style.height = c.h * cp + 'px';
  for (let y = 0; y < c.h; y++) for (let x = 0; x < c.w; x++)
    grid.append(h('div', { class: 'cell' + (c.blocked[y][x] ? ' blocked' : ''), style: `left:${x * cp}px;top:${y * cp}px` }));
  for (const s of c.slots) {
    const it = item(s.arche);
    const img = it.icon ? itemIcon(s.arche) : h('div', { class: 'noicon' }, itemName(s.arche));
    if (s.rot && img.style) { img.style.maxWidth = s.h * cp * 0.88 + 'px'; img.style.maxHeight = s.w * cp * 0.88 + 'px'; }
    const el = h('div', {
      class: 'item' + (s.rot ? ' rot' : '') + (s.guid === selSlot ? ' selected' : ''),
      style: `left:${s.x * cp}px;top:${s.y * cp}px;width:${s.w * cp}px;height:${s.h * cp}px;--tile:${tileColor(s.arche)}`,
    }, img, s.count > 1 ? h('span', { class: 'count' }, s.count) : null);
    el.addEventListener('mousedown', e => startDrag(e, s));
    el.addEventListener('mouseenter', () => showTip(s.arche, s.count));
    el.addEventListener('mouseleave', hideTip);
    grid.append(el);
  }
  grid.onclick = e => { if (placing) dropAt(); else if (e.target === grid || e.target.classList.contains('cell')) selectSlot(null); };
}

function renderList(c, box) {
  const rows = Object.entries(c.totals).sort((a, b) => {
    const ca = CATS.indexOf(catOf(item(a[0]).category)), cb = CATS.indexOf(catOf(item(b[0]).category));
    return ca - cb || itemName(a[0]).localeCompare(itemName(b[0]), lang);
  });
  const list = h('div', { class: 'storage-list' });
  box.append(list);
  if (!rows.length) list.append(h('div', { class: 'empty' }, t('empty_storage')));
  let lastCat = null;
  for (const [a, total] of rows) {
    const it = item(a), cat = catOf(it.category)[0];
    if (cat !== lastCat) { list.append(h('div', { class: 'cat-title' }, t('cat_' + cat))); lastCat = cat; }
    const num = h('input', { type: 'number', min: 0, value: total });
    const set = n => quiet(api('total', { cont: c.guid, arche: a, total: Math.max(0, n) }));
    num.onchange = () => set(parseInt(num.value) || 0);
    const row = h('div', { class: 'store-row' },
      h('div', { class: 'ic', style: `--tile:${tileColor(a)}` }, itemIcon(a)),
      h('div', {},
        h('div', { class: 'nm' }, itemName(a)),
        h('div', { class: 'row' },
          h('button', { class: 'small', onclick: () => set(total - 1) }, '−'), num,
          h('button', { class: 'small', onclick: () => set(total + 1) }, '+'),
          h('button', { class: 'small', onclick: () => set(total + it.stack) }, t('add_stack')),
          h('span', { class: 'hint' }, `${Math.ceil(total / Math.max(1, it.stack))} ${t('stacks')} · ${it.stack}`))));
    row.addEventListener('mouseenter', () => showTip(a, total));
    row.addEventListener('mouseleave', hideTip);
    list.append(row);
  }
}

function renderNamed(c, box) {
  const rack = h('div', { class: 'rack' });
  box.append(rack);
  for (const s of c.slots) {
    const el = h('div', { class: 'rack-slot' + (s.guid === selSlot ? ' selected' : '') + (s.arche ? '' : ' empty'),
      style: s.arche ? `--tile:${tileColor(s.arche)}` : '', onclick: () => selectSlot(s.guid) },
      h('div', { class: 'ic' }, s.arche ? itemIcon(s.arche) : h('span', { class: 'hint' }, '+')),
      h('div', { class: 'nm' }, s.arche ? itemName(s.arche) : t('empty')),
      h('div', { class: 'tagline' }, s.tag.split('.').pop()));
    if (s.arche) { el.addEventListener('mouseenter', () => showTip(s.arche, s.count)); el.addEventListener('mouseleave', hideTip); }
    rack.append(el);
  }
}

// ------------------------------------------------------------------ selection & details
async function selectSlot(guid) {
  selSlot = guid;
  slotInst = null;
  await refreshSlotInst();
  renderContView(); renderDetails();
}

async function refreshSlotInst() {
  if (!selSlot || !ST) { slotInst = null; return; }
  const c = cont();
  const s = c && (c.slots || []).find(x => x.guid === selSlot);
  if (!s || !s.count) { slotInst = []; return; }
  try {
    const r = await fetch('/api/slotinfo', { method: 'POST', body: JSON.stringify({ slot: selSlot }) });
    slotInst = r.ok ? (await r.json()).instances : [];
  } catch (e) { slotInst = []; }
}

function renderDetails() {
  const box = $('#slotDetails'), c = cont();
  const s = c && (c.slots || []).find(x => x.guid === selSlot);
  box.innerHTML = '';
  if (!s) { box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  if (!s.arche) {
    box.append(h('div', { class: 'hint', style: 'grid-column:1/-1' }, t('named_hint')));
    return;
  }
  const it = item(s.arche);
  const controls = h('div', { class: 'row' });
  if (c.kind === 'grid') {
    const num = h('input', { type: 'number', min: 1, max: overStack ? 9999 : it.stack, value: s.count });
    const setCount = n => quiet(api('count', { slot: s.guid, count: n, force: overStack }));
    num.onchange = () => { const n = parseInt(num.value); if (n >= 1) setCount(n); };
    controls.append(h('span', {}, t('count') + ':'),
      h('button', { class: 'small', onclick: () => s.count > 1 && setCount(s.count - 1) }, '−'), num,
      h('button', { class: 'small', onclick: () => setCount(s.count + 1) }, '+'),
      h('button', { class: 'small', onclick: () => setCount(it.stack) }, t('max')),
      h('button', { class: 'small', onclick: () => rotateSelected() }, '⟳ ' + t('rotate')),
      h('button', { class: 'small danger', onclick: () => api('delete', { cont: c.guid, slot: s.guid }).then(() => selectSlot(null), () => {}) }, '✕ ' + t('del')),
      h('label', { class: 'hint' }, h('input', { type: 'checkbox', checked: overStack, onchange: e => { overStack = e.target.checked; renderDetails(); } }), ' ' + t('allow_over')));
  } else {
    controls.append(h('button', { class: 'small danger', onclick: () => quiet(api('named', { slot: s.guid, arche: null })) }, '✕ ' + t('remove')));
  }
  box.append(
    h('div', { class: 'big-icon', style: `--tile:${tileColor(s.arche)}` }, itemIcon(s.arche)),
    h('div', {},
      h('div', { class: 'name' }, itemName(s.arche)),
      h('div', { class: 'desc' }, L(it.desc)),
      h('div', { style: 'margin-bottom:8px' },
        h('span', { class: 'tag' }, `${t('size')}: ${it.size[0]}×${it.size[1]}`),
        h('span', { class: 'tag' }, `${t('stack')}: ${it.stack}`),
        h('span', { class: 'tag' }, t('cat_' + catOf(it.category)[0]))),
      controls),
    h('div', { class: 'instances' }, (slotInst || []).filter(hasEditable).map((inst, i) =>
      instanceEditor(inst, (slotInst.length > 1 ? `${t('item_n')} ${i + 1}` : null)))));
}

const hasEditable = inst => inst.fields.length || inst.effects.length || inst.tintable;

// ------------------------------------------------------------------ instance editor (durability, effects, paint)
function bar(value, max) {
  const pct = max ? Math.max(0, Math.min(100, value / max * 100)) : 0;
  return h('div', { class: 'pbar' }, h('i', { style: `width:${pct}%;background:${pct < 25 ? 'var(--bad)' : pct < 60 ? 'var(--accent)' : 'var(--ok)'}` }));
}

function wearBar(value, max) {
  const pct = max ? Math.max(0, Math.min(100, value / max * 100)) : 0;
  return h('div', { class: 'pbar wear', title: `${fmt(value)} / ${fmt(max)}` }, h('i', { style: `width:${pct}%;background:${pct > 75 ? 'var(--bad)' : 'var(--accent)'}` }));
}

function instanceEditor(inst, title) {
  const box = h('div', { class: 'inst' });
  const head = h('div', { class: 'row inst-head' }, title ? h('b', {}, title) : null);
  if (inst.fields.some(f => ['IP_Durability|:', 'IP_Health|:', 'IP_Fatigue|:', 'IP_Fuelable|:', 'IP_Battery|:'].includes(f.ip)))
    head.append(h('button', { class: 'small', onclick: () => quiet(api('repair', { item: inst.guid })) }, '🔧 ' + t('repair')));
  box.append(head);
  for (const f of inst.fields) {
    const name = f.field.split('|')[0];
    const isFat = f.ip === 'IP_Fatigue|:';
    const val = f.value !== null && f.value !== undefined ? f.value : (isFat ? 0 : f.max);
    const num = h('input', { type: 'number', step: f.kind === 'int' ? 1 : 'any', value: val === undefined || val === null ? '' : +(+val).toFixed(2) });
    num.onchange = () => { if (num.value !== '') quiet(api('prop', { item: inst.guid, ip: f.ip, field: f.field, value: parseFloat(num.value) })); };
    const row = h('div', { class: 'field-row' },
      h('span', { class: 'fl' }, t('f_' + name)),
      f.max ? (isFat ? wearBar(val, f.max) : bar(val, f.max)) : h('span'),
      h('span', { class: 'row' }, num, f.max ? h('span', { class: 'hint' }, '/ ' + fmt(f.max)) : null,
        f.stored ? null : h('span', { class: 'hint' }, ' · ' + t('not_stored'))));
    box.append(row);
  }
  if (inst.tintable) {
    const pals = Object.entries(GD.palettes || {});
    const mk = (kind, cur) => {
      const sel = h('select', {}, h('option', { value: '' }, t('none')));
      for (const [p, info] of pals.filter(([, i]) => i.kind === kind && (kind === 'decal' || i.color)).sort((a, b) => (L(a[1].name) || a[1].id).localeCompare(L(b[1].name) || b[1].id)))
        sel.append(h('option', { value: p, selected: p === cur }, L(info.name) || info.id.replace(/BP_Palette_(Paint|Decal)_/, '')));
      sel.onchange = () => quiet(api('tint', { item: inst.guid, kind, palette: sel.value || null }));
      const info = GD.palettes[cur];
      const sw = info && info.color ? h('span', { class: 'swatch', style: `background:rgb(${info.color.slice(0, 3).map(v => Math.round(Math.min(1, Math.pow(v, 1 / 2.2)) * 255)).join(',')})` }) : null;
      return h('div', { class: 'field-row tint-row' }, h('span', { class: 'fl' }, t(kind)), h('div', { class: 'tint-pick' }, sw, sel));
    };
    if (inst.tintable.paint !== false) box.append(mk('paint', inst.paint));
    if (inst.tintable.decal !== false) box.append(mk('decal', inst.decal));
  }
  // effects: visible ones as chips, internal (game-computed) ones folded into one toggle
  const effs = h('div', { class: 'effects' });
  const hidden = [];
  for (const e of inst.effects) {
    const info = (GD.effects || {})[e.cls] || {};
    if (info.alert === 'Invisible' || info.upgrade) { hidden.push([e, info]); continue; }
    effs.append(effectChip(inst, e, info));
  }
  if (hidden.length) {
    const more = h('span', { class: 'chip dim more' }, `+${hidden.length} ${t('hidden_eff')}`);
    more.onclick = () => { more.replaceWith(...hidden.map(([e, info]) => effectChip(inst, e, info))); };
    effs.append(more);
  }
  // only effects the game allows on this item (IP_StatusEffectCondition), names de-duplicated
  const seen = new Set();
  const legal = (inst.allowedEffects || []).map(cls => [cls, (GD.effects || {})[cls] || {}])
    .filter(([, i]) => L(i.name) && i.alert !== 'Invisible' && !seen.has(L(i.name)) && seen.add(L(i.name)))
    .sort((a, b) => L(a[1].name).localeCompare(L(b[1].name), lang));
  let add;
  if (legal.length) {
    add = h('select', { class: 'add-effect' }, h('option', { value: '' }, t('add_effect')));
    for (const [cls, info] of legal) add.append(h('option', { value: cls, title: L(info.desc) }, L(info.name)));
    add.onchange = () => { if (add.value) quiet(api('effect_add', { item: inst.guid, cls: add.value })); };
  } else add = h('div', { class: 'hint' }, t('no_effects'));
  box.append(h('div', { class: 'effects-block' }, h('div', { class: 'fl' }, t('effects')), effs, add));
  return box;
}

function effectChip(inst, e, info) {
  const col = ALERT_COLORS[info.alert] || ALERT_COLORS.Harmless;
  const chip = h('span', { class: 'chip' + (info.alert === 'Invisible' || info.upgrade ? ' dim' : '') },
    h('span', { class: 'chip-ic' }, info.icon ? icon(info.icon, col) : '◆'),
    L(info.name) || e.cls.split('.').pop().replace(/_C$/, ''),
    h('button', { class: 'x', title: t('del'), onclick: () => quiet(api('effect_remove', { item: inst.guid, effect: e.guid })) }, '×'));
  if (L(info.desc)) chip.title = L(info.desc);
  return chip;
}

// ------------------------------------------------------------------ placing / moving (grid)
function fits(c, x, y, w, hh, ignore) {
  if (x < 0 || y < 0 || x + w > c.w || y + hh > c.h) return false;
  for (let yy = y; yy < y + hh; yy++) for (let xx = x; xx < x + w; xx++) if (c.blocked[yy][xx]) return false;
  return !c.slots.some(s => s.guid !== ignore && x < s.x + s.w && s.x < x + w && y < s.y + s.h && s.y < y + hh);
}

function startPlacing(arche, moveSlot = null, rot = false) {
  placing = { arche, rot, moveSlot };
  const g = $('#ghost');
  g.innerHTML = '';
  g.append(itemIcon(arche));
  g.classList.remove('hidden');
  updateGhost();
  document.body.style.cursor = 'grabbing';
}

function cancelPlacing() {
  placing = null;
  $('#ghost').classList.add('hidden');
  document.body.style.cursor = '';
  for (const el of document.querySelectorAll('.cat-item.active')) el.classList.remove('active');
}

function ghostTarget() {
  const c = cont(), grid = $('#grid');
  if (!c || !placing || !grid) return null;
  let [w, hh] = item(placing.arche).size;
  if (placing.rot) [w, hh] = [hh, w];
  const r = grid.getBoundingClientRect(), cp = cellPx();
  const inside = mouse.x >= r.left && mouse.x < r.right && mouse.y >= r.top && mouse.y < r.bottom;
  const x = Math.round((mouse.x - r.left) / cp - w / 2), y = Math.round((mouse.y - r.top) / cp - hh / 2);
  return { c, w, hh, x, y, inside, r, cp, ok: inside && fits(c, x, y, w, hh, placing.moveSlot) };
}

function updateGhost() {
  const g = $('#ghost'), tg = ghostTarget();
  if (!tg) return;
  g.classList.toggle('rot', placing.rot);
  g.classList.toggle('bad', !tg.ok);
  const left = tg.inside ? tg.r.left + tg.x * tg.cp : mouse.x - tg.w * tg.cp / 2;
  const top = tg.inside ? tg.r.top + tg.y * tg.cp : mouse.y - tg.hh * tg.cp / 2;
  Object.assign(g.style, { left: left + 'px', top: top + 'px', width: tg.w * tg.cp + 'px', height: tg.hh * tg.cp + 'px' });
}

async function dropAt() {
  const tg = ghostTarget();
  if (!tg || !tg.inside) return;
  if (!tg.ok) { toast('✕', true); return; }
  const p = placing;
  if (p.moveSlot) {
    cancelPlacing();
    await quiet(api('move', { cont: tg.c.guid, slot: p.moveSlot, x: tg.x, y: tg.y, rot: p.rot }));
    selectSlot(p.moveSlot);
  } else {
    await quiet(api('place', { cont: tg.c.guid, arche: p.arche, x: tg.x, y: tg.y, rot: p.rot, count: 1 }));
    toast(t('stacked') + ': ' + itemName(p.arche));
    updateGhost();
  }
}

function startDrag(e, s) {
  if (placing || e.button !== 0) return;
  e.preventDefault();
  const sx = e.clientX, sy = e.clientY;
  const mm = ev => {
    if (Math.abs(ev.clientX - sx) + Math.abs(ev.clientY - sy) > 6) {
      cleanup();
      selSlot = s.guid;
      startPlacing(s.arche, s.guid, s.rot);
      const up = () => { document.removeEventListener('mouseup', up); if (placing) { const tg = ghostTarget(); if (tg && tg.ok) dropAt(); else cancelPlacing(); } };
      document.addEventListener('mouseup', up);
    }
  };
  const mu = () => { cleanup(); selectSlot(s.guid); };
  const cleanup = () => { document.removeEventListener('mousemove', mm); document.removeEventListener('mouseup', mu); };
  document.addEventListener('mousemove', mm);
  document.addEventListener('mouseup', mu);
}

function rotateSelected() {
  const c = cont(), s = c && c.kind === 'grid' && c.slots.find(x => x.guid === selSlot);
  if (!s) return;
  let [w, hh] = item(s.arche).size;
  if (!s.rot) [w, hh] = [hh, w];
  const x = Math.round(s.x + s.w / 2 - w / 2), y = Math.round(s.y + s.h / 2 - hh / 2);
  for (const [dx, dy] of [[0, 0], [-1, 0], [0, -1], [-1, -1], [1, 0], [0, 1]])
    if (fits(c, x + dx, y + dy, w, hh, s.guid)) return quiet(api('move', { cont: c.guid, slot: s.guid, x: x + dx, y: y + dy, rot: !s.rot }));
  toast('✕ ' + t('rotate'), true);
}

function onKey(e) {
  if (e.target.matches('input, select, textarea')) return;
  if (e.key === 'Escape') cancelPlacing();
  else if ('rRкК'.includes(e.key) && e.key.length === 1) {
    if (placing) { placing.rot = !placing.rot; updateGhost(); } else rotateSelected();
  } else if ((e.key === 'Delete' || e.key === 'Backspace') && selSlot && !placing && cont() && cont().kind === 'grid') {
    api('delete', { cont: curCont, slot: selSlot }).then(() => selectSlot(null), () => {});
  }
}

// ------------------------------------------------------------------ tooltip
function showTip(arche, count) {
  const it = item(arche), tip = $('#tooltip');
  tip.innerHTML = '';
  tip.append(h('b', {}, itemName(arche) + (count > 1 ? ` ×${count}` : '')), h('span', {}, L(it.desc)));
  tip.classList.remove('hidden');
  const move = () => Object.assign(tip.style, { left: Math.min(mouse.x + 16, innerWidth - 340) + 'px', top: mouse.y + 16 + 'px' });
  move();
  clearInterval(showTip.iv);
  showTip.iv = setInterval(move, 30);
}
function hideTip() { clearInterval(showTip.iv); $('#tooltip').classList.add('hidden'); }

// ------------------------------------------------------------------ catalog
function catalogItems(filterFn) {
  const q = catSearch.trim().toLowerCase();
  return Object.entries(GD.items)
    .filter(([a, it]) => !HIDDEN_ITEM.test(it.id) && (L(it.name) || '').trim())
    .filter(([a, it]) => !filterFn || filterFn(a, it))
    .filter(([a, it]) => catFilter === 'all' || catOf(it.category)[0] === catFilter)
    .filter(([a, it]) => !q || itemName(a).toLowerCase().includes(q) || it.id.toLowerCase().includes(q) || (it.name.en || '').toLowerCase().includes(q))
    .sort((x, y) => itemName(x[0]).localeCompare(itemName(y[0]), lang));
}

function renderCatalog(panel) {
  panel.innerHTML = '';
  const c = cont();
  const partsOnly = c && c.group === 'parts' && c.kind === 'named';
  const search = h('input', { type: 'search', placeholder: t('search'), value: catSearch });
  const list = h('div', { class: 'catalog' });
  const cats = h('div', { class: 'cats' });
  const fill = () => {
    list.innerHTML = '';
    for (const [a, it] of catalogItems(partsOnly ? (a, i) => (i.slots || []).length : null).slice(0, 400)) {
      const el = h('div', { class: 'cat-item' + (placing && placing.arche === a && !placing.moveSlot ? ' active' : '') },
        h('div', { class: 'ic', style: `--tile:${tileColor(a)}` }, itemIcon(a)),
        h('div', { class: 'nm' }, itemName(a)),
        h('div', { class: 'sz' }, `${it.size[0]}×${it.size[1]} · ${it.stack}`));
      el.onclick = () => onCatalogPick(a, el);
      el.addEventListener('mouseenter', () => showTip(a, 0));
      el.addEventListener('mouseleave', hideTip);
      list.append(el);
    }
  };
  for (const key of ['all', ...CATS.map(x => x[0])])
    cats.append(h('button', { class: key === catFilter ? 'active' : '', onclick: () => { catFilter = key; renderCatalog(panel); } },
      key === 'all' ? t('all') : t('cat_' + key)));
  search.oninput = () => { catSearch = search.value; fill(); };
  panel.append(h('h3', {}, t('catalog')), search, cats, list);
  fill();
}

async function onCatalogPick(arche, el) {
  const c = cont();
  if (!c) return;
  if (c.kind === 'grid') {
    for (const x of document.querySelectorAll('.cat-item.active')) x.classList.remove('active');
    el.classList.add('active');
    selSlot = null; renderDetails();
    startPlacing(arche);
    toast(t('placing') + itemName(arche));
  } else if (c.kind === 'list') {
    await quiet(api('total', { cont: c.guid, arche, total: (c.totals[arche] || 0) + item(arche).stack }));
    toast(t('stacked') + ': ' + itemName(arche));
  } else {
    const s = c.slots.find(x => x.guid === selSlot) || c.slots.find(x => !x.arche);
    if (!s) return toast(t('named_hint'), true);
    await quiet(api('named', { slot: s.guid, arche }));
    selectSlot(s.guid);
  }
}

// ------------------------------------------------------------------ car
const CAR_GROUPS = [
  ['car_body', tg => tg.startsWith('Car.Equip.Body.')],
  ['car_ess', tg => tg.startsWith('Car.Equip.Essentials.')],
  ['car_att', tg => tg.startsWith('Car.Equip.Attachments.')],
  ['car_perf', tg => tg.startsWith('Car.Equip.Performance.')],
  ['car_int', tg => tg.startsWith('Car.Equip.Internal.')],
  ['car_cos', tg => tg.startsWith('Car.Equip.Cosmetics.')],
  ['car_other', tg => true],
];
const SLOT_EXTRA = {
  ru: { FuelReserve: 'Резервный бак', BatteryReserve: 'Резервный аккумулятор', Suspension: 'Подвеска', Brakes: 'Тормоза',
    Compass: 'Компас', Speedometer: 'Спидометр', LimBox: 'Индикатор ЛИМ', StatusBox: 'Сигнальные лампы', Radio: 'Радио',
    CarFriend: 'Приборная панель', GobblerScreen: 'Экран АРК', DoctorGobbler: 'Доктор АРК', GoldenGobbler: 'Перегрузчик АРК',
    HealthBox: 'Аптечка', RadBox: 'Счётчик радиации', LargeGadget: 'Большой прибор', SmallGadgetRight: 'Приборная панель (справа)',
    Crafting_TierOne: 'Верстак (ур. 1)', Crafting_TierTwo: 'Верстак (ур. 2)', InventoryStorageTierOne: 'Багажник (ур. 1)',
    InventoryStorageTierTwo: 'Багажник (ур. 2)', InventoryStorageTierThree: 'Багажник (ур. 3)', Gobbler: 'Пассажирское сиденье' },
  en: { FuelReserve: 'Reserve tank', BatteryReserve: 'Reserve battery', Suspension: 'Suspension', Brakes: 'Brakes',
    Compass: 'Compass', Speedometer: 'Speedometer', LimBox: 'LIM gauge', StatusBox: 'Warning lights', Radio: 'Radio',
    CarFriend: 'Dashboard', GobblerScreen: 'ARC screen', DoctorGobbler: 'Doctor ARC', GoldenGobbler: 'ARC overcharger',
    HealthBox: 'First aid box', RadBox: 'Radiation gauge', LargeGadget: 'Large gadget', SmallGadgetRight: 'Right dash',
    Crafting_TierOne: 'Workbench (T1)', Crafting_TierTwo: 'Workbench (T2)', InventoryStorageTierOne: 'Trunk (T1)',
    InventoryStorageTierTwo: 'Trunk (T2)', InventoryStorageTierThree: 'Trunk (T3)', Gobbler: 'Passenger seat' },
};
const slotLabel = tag => {
  const own = L((GD.carslots || {})[tag]);
  if (own) return own;
  const last = tag.split('.').pop();
  const ex = (SLOT_EXTRA[lang] || SLOT_EXTRA[lang === 'uk' ? 'ru' : 'en'] || SLOT_EXTRA.en)[last];
  return ex || last.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2');
};
const isEmptyPart = a => !a || /_Empty$/.test(item(a).id);

function renderCar() {
  renderQuirks();
  const box = $('#carSlots'), car = ST.car;
  box.innerHTML = '';
  if (!car) return;
  for (const [gk, f] of CAR_GROUPS) {
    const slots = car.slots.filter(s => CAR_GROUPS.find(([, g]) => g(s.tag))[0] === gk);
    if (!slots.length) continue;
    const grid = h('div', { class: 'car-grid' });
    for (const s of slots) {
      const inst = s.item, a = inst && inst.arche;
      const hp = inst && inst.fields.find(x => x.ip === 'IP_Health|:');
      const fat = inst && inst.fields.find(x => x.ip === 'IP_Fatigue|:');
      const vis = inst ? inst.effects.filter(e => { const i = (GD.effects || {})[e.cls] || {}; return i.alert && i.alert !== 'Invisible' && !i.upgrade; }) : [];
      grid.append(h('div', { class: 'car-slot' + (s.slot === carSel ? ' selected' : '') + (isEmptyPart(a) ? ' empty' : ''), onclick: () => { carSel = s.slot; renderCar(); } },
        h('div', { class: 'ic', style: a ? `--tile:${tileColor(a)}` : '' }, a && !isEmptyPart(a) ? itemIcon(a) : h('span', { class: 'hint' }, '—')),
        h('div', { class: 'body' },
          h('div', { class: 'slot-name' }, slotLabel(s.tag)),
          h('div', { class: 'nm' }, a && !isEmptyPart(a) ? itemName(a) : t('empty')),
          hp ? bar(hp.value ?? hp.max, hp.max) : null,
          fat && fat.max ? wearBar(fat.value || 0, fat.max) : null,
          vis.length ? h('div', { class: 'mini-effects' }, vis.map(e => { const i = GD.effects[e.cls]; return h('span', { title: L(i.name) }, i.icon ? icon(i.icon, ALERT_COLORS[i.alert]) : '◆'); })) : null)));
    }
    box.append(h('h3', { class: 'car-group' }, t(gk)), grid);
  }
  renderCarEditor();
}

function renderCarEditor() {
  const box = $('#carEditor');
  box.innerHTML = '';
  const s = ST.car && ST.car.slots.find(x => x.slot === carSel);
  if (!s) { box.append(h('div', { class: 'hint' }, t('car_hint'))); return; }
  const a = s.item && s.item.arche;
  box.append(h('h3', {}, slotLabel(s.tag)));
  if (a && !isEmptyPart(a)) {
    box.append(h('div', { class: 'row', style: 'gap:12px;margin-bottom:10px' },
      h('div', { class: 'big-icon', style: `--tile:${tileColor(a)}` }, itemIcon(a)),
      h('div', {}, h('div', { class: 'name' }, itemName(a)), h('div', { class: 'desc' }, L(item(a).desc)))));
    box.append(instanceEditor(s.item, null));
  }
  const parts = Object.keys(GD.items).filter(p => (GD.items[p].slots || []).includes(s.tag));
  if (parts.length) {
    const pick = h('div', { class: 'part-pick' });
    for (const p of parts.sort((x, y) => isEmptyPart(x) - isEmptyPart(y) || itemName(x).localeCompare(itemName(y), lang))) {
      pick.append(h('div', { class: 'cat-item' + (p === a ? ' active' : ''), onclick: () => p !== a && quiet(api('carpart', { slot: s.slot, arche: p })) },
        h('div', { class: 'ic', style: `--tile:${tileColor(p)}` }, isEmptyPart(p) ? '∅' : itemIcon(p)),
        h('div', { class: 'nm' }, isEmptyPart(p) ? t('empty') : itemName(p)),
        GD.items[p].maxHealth ? h('div', { class: 'sz' }, '♥ ' + fmt(GD.items[p].maxHealth)) : null));
    }
    box.append(h('h3', { style: 'margin-top:14px' }, t('compatible')), pick);
  }
}

// ------------------------------------------------------------------ research tree
function nodeState(id) {
  const r = ST.research || {};
  if ((r.installed || []).includes(id)) return 'installed';
  if ((r.purchased || []).includes(id)) return 'researched';
  if ((r.unlocked || []).includes(id)) return 'available';
  return 'locked';
}
const nodeTitle = n => n.kind === 'recipe' ? itemName(n.product) : L(n.name) || n.upgrade.split('.').pop();
const nodeIcon = n => n.kind === 'recipe' ? (item(n.product).icon ? itemIcon(n.product) : h('span', {}, '?')) : (n.icon ? icon(n.icon) : h('span', {}, '⚙'));

function setupResearchCanvas() {
  const cv = $('#researchCanvas');
  let drag = null;
  cv.addEventListener('mousedown', e => { if (e.button === 0) drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false }; });
  window.addEventListener('mousemove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    view.x = drag.vx + dx; view.y = drag.vy + dy; applyView();
  });
  window.addEventListener('mouseup', () => { setTimeout(() => { drag = null; }, 0); });
  cv.addEventListener('click', e => { if (drag && drag.moved) e.stopPropagation(); }, true);
  cv.addEventListener('wheel', e => {
    e.preventDefault();
    const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    const z = Math.min(1.5, Math.max(0.12, view.z * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
    view.x = mx - (mx - view.x) * z / view.z; view.y = my - (my - view.y) * z / view.z; view.z = z;
    applyView();
  }, { passive: false });
}
function applyView() { $('#researchInner').style.transform = `translate(${view.x}px,${view.y}px) scale(${view.z})`; }

function renderResearch() {
  if (!ST || !GD.graph) return;
  const inner = $('#researchInner'), g = GD.graph, N = g.nodes;
  inner.innerHTML = '';
  const xs = Object.values(N).map(n => n.x), ys = Object.values(N).map(n => n.y);
  const minX = Math.min(...xs, ...g.groups.map(x => x.x)) - 200, minY = Math.min(...ys, ...g.groups.map(x => x.y)) - 200;
  const maxX = Math.max(...xs) + 400, maxY = Math.max(...ys) + 400;
  const W = maxX - minX, H = maxY - minY, NS = 104;
  inner.style.width = W + 'px'; inner.style.height = H + 'px';
  if (!view.init) {
    const cv = $('#researchCanvas').getBoundingClientRect();
    view.z = Math.max(0.12, Math.min(cv.width / W, cv.height / H));
    view.x = (cv.width - W * view.z) / 2; view.y = (cv.height - H * view.z) / 2; view.init = true;
  }
  applyView();
  for (const gr of g.groups)
    inner.append(h('div', { class: 'rgroup', style: `left:${gr.x - minX}px;top:${gr.y - minY}px;width:${gr.w}px;height:${gr.h}px` },
      h('div', { class: 'rgroup-title' }, L(gr.title))));
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', W); svg.setAttribute('height', H); svg.setAttribute('class', 'redges');
  for (const n of Object.values(N)) for (const c of n.children) {
    const m = N[c]; if (!m) continue;
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const x1 = n.x - minX + NS / 2, y1 = n.y - minY + NS / 2, x2 = m.x - minX + NS / 2, y2 = m.y - minY + NS / 2;
    line.setAttribute('d', `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`);
    const st = nodeState(n.id) !== 'locked' && nodeState(n.id) !== 'available' ? 'on' : 'off';
    line.setAttribute('class', 'edge ' + st);
    svg.append(line);
  }
  inner.append(svg);
  for (const n of Object.values(N)) {
    const st = nodeState(n.id);
    const el = h('div', { class: `rnode ${st} ${n.kind}` + (n.id === nodeSel ? ' selected' : ''), style: `left:${n.x - minX}px;top:${n.y - minY}px;width:${NS}px;height:${NS}px`,
      onclick: () => { nodeSel = n.id; renderResearch(); } },
      h('div', { class: 'ric' }, nodeIcon(n)),
      h('div', { class: 'rname' }, nodeTitle(n)),
      st === 'installed' ? h('span', { class: 'rbadge' }, '✓') : st === 'researched' && n.kind === 'upgrade' && n.upgrade.includes('/UP_Garage') ? h('span', { class: 'rbadge warn' }, '!') : null);
    inner.append(el);
  }
  const lg = $('#researchLegend');
  lg.innerHTML = '';
  for (const s of ['locked', 'available', 'researched', 'installed']) lg.append(h('span', { class: 'lg ' + s }, t('s_' + s)));
  renderNodePanel();
}

function costList(list) {
  return h('div', { class: 'costs' }, (list || []).map(c => {
    if (c.currency) {
      const info = GD.currencies[c.currency] || {};
      return h('span', { class: 'cost' }, info.icon ? icon(info.icon, info.tint) : '⚡', ` ${fmt(c.qty)} ${L(info.name) || ''}`);
    }
    return h('span', { class: 'cost' }, itemIcon(c.item), ` ${c.qty} × ${itemName(c.item)}`);
  }));
}

function renderNodePanel() {
  const box = $('#nodePanel');
  box.innerHTML = '';
  const n = nodeSel && GD.graph.nodes[nodeSel];
  if (!n) { box.append(h('div', { class: 'hint' }, t('research_hint'))); return; }
  const st = nodeState(n.id);
  const desc = n.kind === 'recipe' ? L(item(n.product).desc) : L(n.desc);
  box.append(
    h('div', { class: 'row', style: 'gap:12px;margin-bottom:8px' },
      h('div', { class: 'big-icon', style: n.kind === 'recipe' ? `--tile:${tileColor(n.product)}` : '' }, nodeIcon(n)),
      h('div', {}, h('div', { class: 'name' }, nodeTitle(n)), h('span', { class: 'tag' }, t('s_' + st)))),
    h('div', { class: 'desc' }, desc));
  const states = h('div', { class: 'switch', style: 'margin:8px 0' });
  for (const s of ['locked', 'available', 'researched'])
    states.append(h('button', { class: (st === s || (s === 'researched' && st === 'installed')) ? 'on' : '',
      onclick: () => quiet(api('research', { node: n.id, state: s })) }, t('s_' + s)));
  box.append(states);
  if (n.kind === 'upgrade' && n.upgrade.includes('/UP_Garage')) {
    box.append(h('label', { class: 'row', style: 'margin:6px 0' },
      h('input', { type: 'checkbox', checked: st === 'installed', onchange: e => quiet(api('install', { node: n.id, on: e.target.checked })) }),
      ' ' + t('installed_q')),
      h('div', { class: 'hint' }, t('install_note')));
    if (/InventoryExpansion|InventoryParts|InventoryStarter/.test(n.upgrade)) box.append(h('div', { class: 'hint' }, t('layout_note')));
  }
  box.append(reasonsBlock(n, st));
  if ((n.research || []).length) box.append(h('h3', { style: 'margin-top:12px' }, t('research_cost')), costList(n.research));
  if ((n.craft || []).length) box.append(h('h3', { style: 'margin-top:12px' }, t('craft_cost')), costList(n.craft));
}

// entries of the logbook that satisfy a scan tag
let TAG2ENTRIES = null;
function tagEntries(tag) {
  if (!TAG2ENTRIES) {
    TAG2ENTRIES = {};
    for (const [p, e] of Object.entries(GD.logbook.entries)) if (e.unlockTag) (TAG2ENTRIES[e.unlockTag] = TAG2ENTRIES[e.unlockTag] || []).push(p);
  }
  return TAG2ENTRIES[tag] || [];
}
const openLog = () => new Set((ST.logbook || []).map(e => e.path));
function conditionDone(c) {
  const tags = c.tags || [];
  if (!tags.length) return null;          // not machine-checkable
  const wb = ST.whiteboard || {}, opened = openLog();
  return tags.some(tg => (wb[tg] || 0) > 0 || tagEntries(tg).some(p => opened.has(p)));
}

function reasonsBlock(n, st) {
  const box = h('div', { class: 'reasons' });
  const parents = Object.values(GD.graph.nodes).filter(p => p.children.includes(n.id));
  const conds = n.conditions || [];
  if (st === 'locked' || conds.length || parents.length) box.append(h('h3', { style: 'margin-top:12px' }, st === 'locked' ? t('why') : t('conditions')));
  if (n.byDefault) box.append(h('div', { class: 'hint' }, '✓ ' + t('by_default')));
  if (parents.length) {
    const anyDone = parents.some(p => ['researched', 'installed'].includes(nodeState(p.id)));
    box.append(h('div', { class: 'reason ' + (anyDone ? 'ok' : 'no') }, (anyDone ? '✓ ' : '✗ ') + t('parents') + (anyDone ? '' : ' — ' + t('parent_needed'))));
    for (const p of parents)
      box.append(h('div', { class: 'reason-sub', onclick: () => { nodeSel = p.id; renderResearch(); } },
        h('span', { class: 'lgdot ' + nodeState(p.id) }), nodeTitle(p), h('small', { class: 'hint' }, ' · ' + t('s_' + nodeState(p.id)))));
  }
  for (const c of conds) {
    const done = conditionDone(c);
    const row = h('div', { class: 'reason ' + (done === null ? '' : done ? 'ok' : 'no') },
      (done === null ? '• ' : done ? '✓ ' : '✗ ') + (L(c.text) || '?'),
      done === null ? h('small', { class: 'hint' }, ' — ' + t('cond_manual')) : null);
    box.append(row);
    if (done === false) {
      const paths = (c.tags || []).flatMap(tagEntries);
      if (paths.length) box.append(h('button', { class: 'small', onclick: () => quiet(api('logmany', { paths, on: true })) }, '📖 ' + t('open_entry')));
    }
  }
  if (st === 'locked') box.append(h('button', { class: 'small', style: 'margin-top:6px', onclick: () => quiet(api('research', { node: n.id, state: 'available' })) }, t('make_available')));
  return box;
}

// ------------------------------------------------------------------ logbook (codex)
let codexCat = null, codexSub = null, codexSel = null, codexFilter = 'all', codexSearch = '';
const entryName = (p, e) => e.item ? itemName(p) : (L(e.name) || p.split('.').pop());
const entryIcon = (p, e) => e.item ? itemIcon(p) : (e.icon ? icon(e.icon, e.tint) : h('span', { class: 'hint' }, '?'));

function renderCodex() {
  if (!GD.logbook) return;
  const LB = GD.logbook, opened = openLog();
  const all = Object.entries(LB.entries);
  if (!codexCat) codexCat = LB.categories[0].tag;
  // categories
  const cbox = $('#codexCats');
  cbox.innerHTML = '';
  cbox.append(h('h3', {}, t('tab_codex')));
  for (const c of LB.categories) {
    const es = all.filter(([, e]) => e.cat === c.tag);
    if (!es.length) continue;
    const open = es.filter(([p]) => opened.has(p)).length;
    cbox.append(h('button', { class: 'cont-btn codex-cat' + (c.tag === codexCat ? ' active' : ''), onclick: () => { codexCat = c.tag; codexSub = null; renderCodex(); } },
      h('span', { class: 'row' }, c.icon ? h('span', { class: 'cat-ic' }, icon(c.icon)) : null, L(c.name)), h('small', {}, `${open}/${es.length}`)));
    if (c.tag === codexCat) {
      const subs = LB.subcategories.filter(sc => es.some(([, e]) => e.sub === sc.tag));
      for (const sc of subs) {
        const ss = es.filter(([, e]) => e.sub === sc.tag);
        cbox.append(h('button', { class: 'cont-btn sub' + (sc.tag === codexSub ? ' active' : ''), onclick: () => { codexSub = codexSub === sc.tag ? null : sc.tag; renderCodex(); } },
          L(sc.name) || sc.id, h('small', {}, `${ss.filter(([p]) => opened.has(p)).length}/${ss.length}`)));
      }
    }
  }
  // grid
  const cat = LB.categories.find(c => c.tag === codexCat) || {};
  $('#codexTitle').textContent = L(cat.name) + (codexSub ? ' · ' + L((LB.subcategories.find(s => s.tag === codexSub) || {}).name) : '');
  const q = codexSearch.toLowerCase();
  const list = all.filter(([p, e]) => e.cat === codexCat && (!codexSub || e.sub === codexSub))
    .filter(([p]) => codexFilter === 'all' || (codexFilter === 'open') === opened.has(p))
    .filter(([p, e]) => !q || entryName(p, e).toLowerCase().includes(q))
    .sort((a, b) => entryName(a[0], a[1]).localeCompare(entryName(b[0], b[1]), lang));
  const tools = $('#codexTools');
  tools.innerHTML = '';
  const search = h('input', { type: 'search', placeholder: t('search'), value: codexSearch });
  search.oninput = () => { codexSearch = search.value; renderCodex(); };
  const filt = h('div', { class: 'switch' }, ['all', 'open', 'closed'].map(f => h('button', { class: f === codexFilter ? 'on' : '', onclick: () => { codexFilter = f; renderCodex(); } }, t(f === 'all' ? 'c_all' : f === 'open' ? 'c_open' : 'c_closed'))));
  const paths = list.map(([p]) => p);
  tools.append(search, filt,
    h('button', { class: 'small', onclick: () => quiet(api('logmany', { paths: paths.filter(p => !opened.has(p)), on: true })) }, t('open_all')),
    h('button', { class: 'small danger', onclick: () => confirm(t('c_confirm_close')) && quiet(api('logmany', { paths: paths.filter(p => opened.has(p)), on: false })) }, t('close_all')));
  const grid = $('#codexGrid');
  grid.innerHTML = '';
  for (const [p, e] of list) {
    const isOpen = opened.has(p);
    const ent = (ST.logbook || []).find(x => x.path === p);
    grid.append(h('div', { class: 'codex-item' + (isOpen ? '' : ' locked') + (p === codexSel ? ' selected' : '') + (ent && !ent.ack ? ' unread' : ''),
      onclick: () => { codexSel = p; renderCodex(); } },
      h('div', { class: 'ic', style: e.item ? `--tile:${tileColor(p)}` : '' }, entryIcon(p, e)),
      h('div', { class: 'nm' }, entryName(p, e))));
  }
  if (search.value) setTimeout(() => { const s2 = $('#codexTools input[type=search]'); if (s2 && document.activeElement !== s2) { s2.focus(); s2.setSelectionRange(s2.value.length, s2.value.length); } }, 0);
  renderCodexEntry();
}
function renderCodexEntry() {
  const box = $('#codexEntry');
  box.innerHTML = '';
  const p = codexSel, e = p && GD.logbook.entries[p];
  if (!e) return;
  const ent = (ST.logbook || []).find(x => x.path === p);
  const desc = e.item ? L(item(p).desc) : L(e.desc);
  box.append(h('div', { class: 'row', style: 'gap:12px;margin-bottom:8px' },
    h('div', { class: 'big-icon', style: e.item ? `--tile:${tileColor(p)}` : '' }, entryIcon(p, e)),
    h('div', {}, h('div', { class: 'name' }, entryName(p, e)), h('span', { class: 'tag' }, ent ? t('c_opened') : t('c_locked')),
      ent && ent.img ? h('span', { class: 'tag' }, t('c_photo')) : null)));
  box.append(h('div', { class: 'row', style: 'margin:6px 0' },
    h('label', { class: 'row' }, h('input', { type: 'checkbox', checked: !!ent, onchange: ev => quiet(api('log', { path: p, on: ev.target.checked })) }), ' ' + t('c_opened')),
    ent ? h('label', { class: 'row' }, h('input', { type: 'checkbox', checked: ent.ack, onchange: ev => quiet(api('logack', { path: p, on: ev.target.checked })) }), ' ' + t('c_read')) : null));
  if (ent) box.append(h('div', { class: 'hint' }, `${t('c_date')}: ${ent.ts.split('.').slice(0, 3).join('.').replace('-', ' ')}`));
  if (desc) box.append(h('div', { class: 'desc', style: 'margin-top:8px' }, desc));
  if (L(e.lore)) box.append(h('div', { class: 'lore' }, L(e.lore)));
  if ((e.lines || []).length) box.append(h('div', { class: 'transcript' }, e.lines.map(l => h('p', {}, L(l)))));
  if (e.unlockTag) {
    const needed = Object.values(GD.graph.nodes).filter(n => (n.conditions || []).some(c => (c.tags || []).includes(e.unlockTag)));
    if (needed.length) box.append(h('h3', { style: 'margin-top:12px' }, t('c_needed')),
      ...needed.map(n => h('div', { class: 'reason-sub', onclick: () => { nodeSel = n.id; switchTab('research'); } }, h('span', { class: 'lgdot ' + nodeState(n.id) }), nodeTitle(n))));
  }
}

// ------------------------------------------------------------------ economy
function renderEconomy() {
  const cl = $('#currencyList'), rl = $('#resourceList');
  cl.innerHTML = ''; rl.innerHTML = '';
  for (const c of ST.currencies) {
    const info = GD.currencies[c.arche] || {};
    const name = info.id === 'CA_MechXP' ? t('mechxp') : (L(info.name) || (info.id || c.arche));
    const num = h('input', { type: 'number', min: 0, value: c.value, style: 'width:150px' });
    num.onchange = () => quiet(api('currency', { arche: c.arche, value: parseInt(num.value) || 0 }));
    cl.append(h('div', { class: 'card' },
      h('div', { class: 'ic' }, info.icon ? icon(info.icon, info.tint) : h('span', { class: 'glyph' }, '⚙')),
      h('div', {}, h('div', { class: 'nm' }, name), num)));
  }
  const main = ['PlayerHealth', 'CarHealth', 'CarLim', 'Fuel', 'Shield'];
  const glyph = { PlayerHealth: '✚', CarHealth: '🔧', CarLim: '⚡', Fuel: '⛽', Shield: '🛡' };
  const card = r => {
    const num = h('input', { type: 'number', step: 'any', value: Math.round(r.value * 100) / 100 });
    num.onchange = () => quiet(api('resource', { name: r.name, value: parseFloat(num.value) || 0 }));
    const label = t('res_' + r.name);
    return h('div', { class: 'card' }, h('div', { class: 'ic' }, h('span', { class: 'glyph' }, glyph[r.name] || '•')),
      h('div', {}, h('div', { class: 'nm' }, label !== 'res_' + r.name ? label : r.name), num));
  };
  ST.resources.filter(r => main.includes(r.name)).forEach(r => rl.append(card(r)));
  const more = ST.resources.filter(r => !main.includes(r.name));
  if (more.length) {
    const inner = h('div', { class: 'cards', style: 'margin-top:8px' });
    more.forEach(r => inner.append(card(r)));
    rl.append(h('details', { style: 'grid-column:1/-1' }, h('summary', { class: 'hint' }, t('res_more')), inner));
  }
}

// ------------------------------------------------------------------ settings
const truthy = v => v === true || v === 'true' || v === '1' || v === 1;

function renderSettings() {
  const pl = $('#presetList'), sl = $('#settingsList');
  pl.innerHTML = ''; sl.innerHTML = '';
  $('#presetTitle').textContent = L(GD.strings.preset) || 'Preset';
  const s = ST.settings || {};
  const presetId = s.preset || 'standard';
  const preset = GD.presets[presetId] || { settings: {} };
  const ov = s.overrides || {};
  for (const id of PRESET_ORDER.filter(p => GD.presets[p])) {
    const p = GD.presets[id];
    const bars = h('div', { class: 'bars' });
    for (const [k, v] of Object.entries(p.summaries || {})) {
      const key = 'summary_' + k.toLowerCase().replace('environmentalhazards', 'environmnetalhazards');
      bars.append(h('span', {}, L(GD.strings[key]) || k), h('div', { class: 'bar' }, h('i', { style: `width:${Math.round(v * 100)}%` })));
    }
    pl.append(h('div', { class: 'preset' + (id === presetId ? ' active' : ''), onclick: () => id !== presetId && quiet(api('settings', { preset: id })) },
      h('div', { class: 'preset-title' }, L(p.title) || id), h('div', { class: 'short' }, L(p.short) || L(p.desc)), bars));
  }
  sl.append(h('p', { class: 'hint' }, t('preset_note')));
  const base = v => (preset.settings && preset.settings[v] !== undefined) ? String(preset.settings[v]) : DEFAULTS[v];
  const setOv = (v, val) => {
    const next = Object.assign({}, ov);
    if (val === null || String(val) === String(base(v))) delete next[v]; else next[v] = String(val);
    quiet(api('settings', { overrides: next }));
  };
  for (const cat of GD.settings) {
    const items = cat.items.filter(i => i.kind !== 'enumstring' && i.kind !== 'button');
    if (!items.length) continue;
    const box = h('div', { class: 'set-cat' }, h('h3', {}, L(cat.title) || cat.id));
    for (const it of items) {
      const cur = ov[it.var] !== undefined ? ov[it.var] : base(it.var);
      let ctrl;
      if (it.kind === 'checkbox') {
        const on = truthy(cur), asBool = it.var.startsWith('b');
        ctrl = h('div', { class: 'switch' },
          h('button', { class: on ? 'on' : '', onclick: () => setOv(it.var, asBool ? 'true' : '1') }, t('on')),
          h('button', { class: !on ? 'on' : '', onclick: () => setOv(it.var, asBool ? 'false' : '0') }, t('off')));
      } else if (it.kind === 'slider') {
        const min = it.min || 0, max = it.max || 5, step = it.resolution || 0.05;
        const v = cur !== undefined ? parseFloat(cur) : 1;
        const out = h('span', { class: 'val' }, v.toFixed(2));
        const r = h('input', { type: 'range', min, max, step, value: v });
        r.oninput = () => { out.textContent = parseFloat(r.value).toFixed(2); };
        r.onchange = () => setOv(it.var, +parseFloat(r.value).toFixed(3));
        ctrl = h('div', { class: 'row' }, r, out);
      } else if (it.kind === 'enum') {
        const sel = h('select');
        for (const idx of (it.order || it.values.map((_, i) => i))) {
          const label = (it.value_texts && L(it.value_texts[idx])) || it.values[idx] || String(idx);
          sel.append(h('option', { value: idx, selected: String(idx) === String(cur) }, label));
        }
        sel.onchange = () => setOv(it.var, sel.value);
        ctrl = sel;
      } else continue;
      const changed = ov[it.var] !== undefined;
      box.append(h('div', { class: 'set-row' + (changed ? ' changed' : ''), title: it.var },
        h('div', {}, h('div', { class: 't' }, L(it.title) || it.var), h('div', { class: 'd' }, L(it.desc))),
        ctrl,
        changed ? h('button', { class: 'ghost reset', title: t('reset'), onclick: () => setOv(it.var, null) }, '↺') : h('span')));
    }
    sl.append(box);
  }
}

// ------------------------------------------------------------------ summary
function renderSummary() {
  const m = ST.meta || {}, box = $('#summary');
  box.innerHTML = '';
  const pt = m.playtime || 0;
  const rows = [
    [t('file'), ST.path], [t('last_played'), m.lastPlayed], [t('playtime'), `${Math.floor(pt / 3600)} ${t('h')} ${Math.floor(pt / 60) % 60} ${t('m')}`],
    [t('level'), m.level], [t('runs'), m.runs], [t('miles'), m.miles && m.miles.toFixed(1)], [t('mission'), m.mission], [t('build'), m.build],
  ];
  const g = h('div', { class: 'summary-grid' });
  for (const [k, v] of rows) g.append(h('div', {}, k), h('div', {}, v === undefined || v === null ? '—' : v));
  box.append(g, h('p', { class: 'hint', style: 'margin-top:16px' }, `PD Save Editor ${GD.version || ''}`),
    h('button', { class: 'small', onclick: () => showSetup(true) }, t('redo_setup')));
}

boot();


// ------------------------------------------------------------------ statistics (progress whiteboard)
const G = k => () => L(GD.strings['ui.run_finished_' + k]);
const DMG = { ru: { Phys: 'физический', Elec: 'электрический', Rad: 'радиация', Acid: 'кислота', Explo: 'взрывы', Pierce: 'проколы', Heal: 'восстановлено' },
  en: { Phys: 'physical', Elec: 'electrical', Rad: 'radiation', Acid: 'acid', Explo: 'explosive', Pierce: 'piercing', Heal: 'healed' } };
const SL = { // own labels where the game has none (ru / en)
  CarDriveMileage: G('success_stat_dist_driven'), PlayerWalkMileage: G('success_stat_dist_walked'), TopSpeed: G('context_stat_car_speed'),
  CarAirtime: G('context_stat_car_airtime'), CarDriveIncline: G('context_stat_car_incline'), KicksLanded: G('context_stat_player_kicks'),
  AnomaliesLured: G('context_stat_anoms_flared'), CarPartsBroken: G('context_stat_car_parts_broken'),
  'StatusEffects.Afflicted': G('context_stat_statuseffects_afflicted'), 'StatusEffects.Cured': G('context_stat_statuseffects_cured'),
  'Quirks.QuirkTriggersExperienced': G('context_stat_quirk_invokes'),
  'LIM.Gained': ['ЛИМ получено (кЛИМ)', 'LIM gained (kLIM)'], 'LIM.Spent': ['ЛИМ потрачено (кЛИМ)', 'LIM spent (kLIM)'],
  'Fuel.Gained': ['Топлива заправлено', 'Fuel gained'], 'Fuel.Spent': ['Топлива израсходовано', 'Fuel spent'],
  'Currency.AnchorJuice.Stable': ['Собрано стабильной энергии', 'Stable energy collected'],
  'Currency.AnchorJuice.Unstable': ['Собрано нестабильной энергии', 'Unstable energy collected'],
  'Currency.AnchorJuice.Corrupted': ['Собрано дефектной энергии', 'Corrupted energy collected'],
  'Quirks.QuirksActive': ['Активных парадоксов', 'Active quirks'], 'Quirks.QuirksCured': ['Вылечено парадоксов', 'Quirks cured'],
  'Quirks.QuirkedRunsStreak': ['Заездов подряд с парадоксами', 'Quirked runs in a row'],
  'Quirks.QuirkedRunsSinceDiagnoseAttempt': ['Заездов с последней диагностики', 'Runs since last diagnosis'],
  'Quirks.RunWithoutRollStreak': ['Заездов без нового парадокса', 'Runs without a new quirk'],
  'Quirks.GraduatedBeginnerPool': ['Пройден набор «для новичков»', 'Beginner quirk pool done'],
  'Loot.LeechCosmeticSpawned': ['Выпало украшений с пиявок', 'Leech cosmetics dropped'],
};
const statLabel = key => {
  const v = SL[key];
  if (typeof v === 'function') return v() || key;
  if (Array.isArray(v)) return lang === 'ru' || lang === 'uk' ? v[0] : v[1];
  const m = key.match(/^(Car|Player)Damage\.(\w+)$/);
  if (m) {
    const d = (DMG[lang === 'uk' ? 'ru' : lang] || DMG.en)[m[2]] || m[2];
    const who = lang === 'ru' || lang === 'uk' ? (m[1] === 'Car' ? 'Урон машине' : 'Урон игроку') : (m[1] === 'Car' ? 'Car damage' : 'Player damage');
    return m[2] === 'Heal' ? (lang === 'ru' || lang === 'uk' ? (m[1] === 'Car' ? 'Машине восстановлено' : 'Игроку восстановлено') : who + ': healed') : `${who}: ${d}`;
  }
  return key.replace(/\./g, ' · ');
};
const STAT_GROUPS = [
  ['st_car', k => /^(CarDriveMileage|TopSpeed|CarAirtime|CarDriveIncline|CarPartsBroken|CarDamage\.)/.test(k)],
  ['st_player', k => /^(PlayerWalkMileage|KicksLanded|PlayerDamage\.)/.test(k)],
  ['st_res', k => /^(LIM\.|Fuel\.|Currency\.)/.test(k)],
  ['st_anom', k => /^(AnomaliesLured|StatusEffects\.)/.test(k)],
  ['st_quirks', k => /^Quirks\./.test(k)],
  ['st_other', k => true],
];

function statInput(tag, v) {
  const num = h('input', { type: 'number', step: 'any', value: +(+v).toFixed(2) });
  num.onchange = () => quiet(api('wb', { tag, value: parseFloat(num.value) || 0 }));
  return num;
}

function renderStats() {
  const box = $('#statsMain');
  if (!box) return;
  box.innerHTML = '';
  const wb = ST.whiteboard || {};
  const P = 'WB.Statistics.';
  // runs table
  const kinds = [['', 'r_all'], ['.CritPathRuns', 'r_crit'], ['.SupplyRuns', 'r_supply'], ['.ExpeditionRuns', 'r_exp']];
  const cols = [['', 'c_total'], ['.Successful', 'c_succ'], ['.Failed', 'c_fail'], ['.SuccessfulStreak', 'c_sstreak'], ['.FailedStreak', 'c_fstreak']];
  const table = h('table', { class: 'stat-table' }, h('tr', {}, h('th'), cols.map(([, c]) => h('th', {}, t(c)))));
  for (const [k, lab] of kinds) {
    const base = P + 'TotalRuns' + k;
    if (!(base in wb)) continue;
    table.append(h('tr', {}, h('td', {}, t(lab)), cols.map(([c]) => h('td', {}, base + c in wb ? statInput(base + c, wb[base + c]) : '—'))));
  }
  box.append(h('h3', { class: 'car-group' }, t('st_runs')), table);
  const rest = Object.keys(wb).filter(k => k.startsWith(P) && !k.startsWith(P + 'TotalRuns')).map(k => k.slice(P.length));
  for (const [g, f] of STAT_GROUPS) {
    const keys = rest.filter(k => STAT_GROUPS.find(([, ff]) => ff(k))[0] === g);
    if (!keys.length) continue;
    const grid = h('div', { class: 'stat-grid' });
    for (const k of keys.sort((a, b) => statLabel(a).localeCompare(statLabel(b), lang)))
      grid.append(h('div', { class: 'stat-row', title: P + k }, h('span', {}, statLabel(k)), statInput(P + k, wb[P + k])));
    box.append(h('h3', { class: 'car-group' }, t(g)), grid);
  }
  renderWbAll();
}

let wbFilter = 'WB.Scanning', wbSearch = '';
function renderWbAll() {
  const box = $('#wbAll');
  if (!box || !$('#wbDetails').open) { if ($('#wbDetails')) $('#wbDetails').ontoggle = () => renderWbAll(); return; }
  box.innerHTML = '';
  const wb = ST.whiteboard || {};
  const groups = {};
  for (const k of Object.keys(wb)) { const g = k.split('.').slice(0, 2).join('.'); groups[g] = (groups[g] || 0) + 1; }
  box.append(h('p', { class: 'hint warn' }, '⚠ ' + t('wb_warn')));
  const chips = h('div', { class: 'cats' });
  for (const [g, n] of Object.entries(groups).sort((a, b) => b[1] - a[1]))
    chips.append(h('button', { class: g === wbFilter ? 'active' : '', onclick: () => { wbFilter = g; renderWbAll(); } }, `${g.replace('WB.', '')} (${n})`));
  const search = h('input', { type: 'search', placeholder: t('search'), value: wbSearch });
  search.oninput = () => { wbSearch = search.value; renderWbAll(); const s2 = $('#wbAll input[type=search]'); s2.focus(); s2.setSelectionRange(s2.value.length, s2.value.length); };
  const tagIn = h('input', { type: 'text', placeholder: t('wb_tag'), style: 'width:360px' });
  const valIn = h('input', { type: 'number', step: 'any', placeholder: t('wb_value'), value: 1 });
  box.append(chips, h('div', { class: 'row', style: 'margin:8px 0' }, search, h('span', { style: 'flex:1' }), tagIn, valIn,
    h('button', { class: 'small', onclick: () => tagIn.value && quiet(api('wb', { tag: tagIn.value.trim(), value: parseFloat(valIn.value) || 0 })) }, '+ ' + t('wb_add'))));
  const q = wbSearch.toLowerCase();
  const list = h('div', { class: 'wb-list' });
  const keys = Object.keys(wb).filter(k => (q ? k.toLowerCase().includes(q) : k.startsWith(wbFilter + '.') || k === wbFilter)).sort();
  for (const k of keys.slice(0, 600))
    list.append(h('div', { class: 'wb-row' }, h('code', {}, k), statInput(k, wb[k]),
      h('button', { class: 'small ghost', title: t('del'), onclick: () => quiet(api('wb', { tag: k, value: null })) }, '✕')));
  box.append(list);
}


// ------------------------------------------------------------------ car quirks
const QD = () => GD.quirks || { conditions: {}, behaviors: {} };
const qPart = (e, kind) => { const d = QD()[kind][e] || {}; return [L(d.partName) || '?', L(d.typeName) || (d.id || e || '?').replace(/^Q[CB]_|_C$/g, '')]; };
function quirkSentence(qc, qb) {
  const [bp, bt] = qPart(qb, 'behaviors'), [cp, ct] = qPart(qc, 'conditions');
  const fmtS = L(QD().sentence) || '{initial_quirk_part} {behaves} when {other_car_part} {conditionally_behaves}';
  const out = fmtS.replace('{initial_quirk_part}', bp).replace('{behaves}', bt.toLowerCase())
    .replace('{other_car_part}', cp.toLowerCase()).replace('{conditionally_behaves}', ct.toLowerCase());
  return out.charAt(0).toUpperCase() + out.slice(1);
}
let qNewC = '', qNewB = '', qNewDiag = false;
function quirkBanned(qc, qb) {
  const c = QD().conditions[qc], b = QD().behaviors[qb];
  if (!c || !b) return false;
  const tags = [c.tag, c.part, c.type].filter(Boolean);
  if ((b.banned || []).some(x => tags.some(tg => tg === x || tg.startsWith(x + '.')))) return true;
  return false;
}

function renderQuirks() {
  const box = $('#quirksBox');
  if (!box) return;
  box.innerHTML = '';
  const q = ST.quirks;
  if (!q) return;
  box.append(h('h3', { class: 'car-group' }, '⚠ ' + (L(GD.strings.quirks_title) || t('st_quirks'))));
  const list = h('div', { class: 'quirk-list' });
  if (!q.active.length) list.append(h('div', { class: 'hint' }, t('q_none')));
  for (const a of q.active) {
    const cure = h('div', { class: 'row' }, h('span', { class: 'hint' }, t('q_cure') + ':'));
    for (const [arche, n] of a.cure) {
      const num = h('input', { type: 'number', min: 0, value: n, style: 'width:56px' });
      num.onchange = () => quiet(api('quirk_curelist', { quirk: a.guid, cure: a.cure.map(([x, k]) => [x, x === arche ? parseInt(num.value) || 0 : k]) }));
      cure.append(h('span', { class: 'cure-item', title: itemName(arche) }, itemIcon(arche), num));
    }
    list.append(h('div', { class: 'quirk' + (a.diagnosed ? ' diag' : '') },
      h('div', { class: 'quirk-text' }, a.diagnosed ? quirkSentence(a.condition, a.behavior) : h('span', {}, h('span', { class: 'qmask' }, '??? '), quirkSentence(a.condition, a.behavior))),
      h('div', { class: 'row', style: 'justify-content:space-between' },
        h('span', { class: 'hint' }, `${fmt(a.invocations)} ${t('q_invocations')} · ${a.diagnosed ? t('q_diag') : t('q_undiag')}`),
        h('span', { class: 'row' },
          h('button', { class: 'small', onclick: () => quiet(api('quirk_diag', { quirk: a.guid, on: !a.diagnosed })) }, a.diagnosed ? '✕ ' + t('q_diag') : '🔍 ' + t('q_diagnose')),
          h('button', { class: 'small primary', onclick: () => quiet(api('quirk_cure', { quirk: a.guid })) }, '🔧 ' + t('q_fix')))),
      cure));
  }
  box.append(list);
  // add a quirk
  const sc = h('select', {}, h('option', { value: '' }, t('q_when') + '…'));
  const sb = h('select', {}, h('option', { value: '' }, t('q_what') + '…'));
  const byLabel = (kind, ent) => ent.filter(([, d]) => d.tag).sort((x, y) => qPart(x[0], kind).join(' ').localeCompare(qPart(y[0], kind).join(' '), lang));
  for (const [c] of byLabel('conditions', Object.entries(QD().conditions))) sc.append(h('option', { value: c, selected: c === qNewC }, qPart(c, 'conditions').join(': ')));
  for (const [b] of byLabel('behaviors', Object.entries(QD().behaviors))) sb.append(h('option', { value: b, selected: b === qNewB }, qPart(b, 'behaviors').join(': ')));
  const preview = h('div', { class: 'hint' }, qNewC && qNewB ? '→ ' + quirkSentence(qNewC, qNewB) + (quirkBanned(qNewC, qNewB) ? '  ⚠ ' + t('q_banned') : '') : '');
  sc.onchange = () => { qNewC = sc.value; renderQuirks(); };
  sb.onchange = () => { qNewB = sb.value; renderQuirks(); };
  box.append(h('div', { class: 'quirk-add' }, h('b', {}, t('q_add')), h('div', { class: 'row' }, sb, h('span', {}, '⟵'), sc,
    h('label', { class: 'hint' }, h('input', { type: 'checkbox', checked: qNewDiag, onchange: e => { qNewDiag = e.target.checked; } }), ' ' + t('q_add_diag')),
    h('button', { class: 'small', disabled: !(qNewC && qNewB), onclick: () => quiet(api('quirk_add', { condition: qNewC, behavior: qNewB, diagnosed: qNewDiag })) }, t('q_add_btn'))), preview));
  // flags + graveyard
  const flags = h('div', { class: 'row' }, h('span', { class: 'hint' }, t('q_flags') + ':'));
  for (const [k, v] of Object.entries(q.flags))
    flags.append(h('label', { class: 'row' }, h('input', { type: 'checkbox', checked: v, onchange: e => quiet(api('quirk_flag', { name: k, on: e.target.checked })) }), ' ' + t('f_' + k)));
  const grave = h('details', {}, h('summary', { class: 'hint' }, `${t('q_grave')} (${q.graveyard.length})`),
    ...q.graveyard.map(g => h('div', { class: 'grave-row' }, quirkSentence(g.condition, g.behavior),
      h('small', { class: 'hint' }, ` · ${fmt(g.invocations)} ${t('q_invocations')} · ${g.revivals} ${t('q_revivals')}`),
      h('button', { class: 'small ghost', title: t('del'), onclick: () => quiet(api('quirk_grave_del', { condition: g.condition, behavior: g.behavior })) }, '✕'))));
  box.append(flags, grave);
}


// ------------------------------------------------------------------ first-run setup (extract game data)
async function showSetup(force = false) {
  const box = $('#setup');
  box.classList.remove('hidden');
  const st = await (await fetch('/api/setup_status', { method: 'POST', body: '{}' })).json();
  let chosen = st.candidates[0] || '';
  const custom = h('input', { type: 'text', value: chosen, style: 'width:100%' });
  const logBox = h('pre', { class: 'setup-log' });
  const status = h('div', { class: 'hint' });
  const go = h('button', { class: 'primary' }, t('setup_go'));
  const list = h('div', { class: 'setup-list' });
  for (const c of st.candidates)
    list.append(h('label', { class: 'row' }, h('input', { type: 'radio', name: 'gamedir', checked: c === chosen,
      onchange: () => { chosen = c; custom.value = c; } }), ' ' + c));
  const poll = async () => {
    const s = await (await fetch('/api/setup_status', { method: 'POST', body: '{}' })).json();
    logBox.textContent = s.log.join('\n');
    logBox.scrollTop = logBox.scrollHeight;
    if (s.running) return setTimeout(poll, 500);
    go.disabled = false;
    if (s.error) { status.textContent = '✕ ' + s.error; status.className = 'hint warn'; return; }
    if (s.ready) { status.textContent = t('setup_done'); setTimeout(() => location.reload(), 800); }
  };
  go.onclick = async () => {
    go.disabled = true;
    status.textContent = t('setup_running'); status.className = 'hint';
    const r = await fetch('/api/setup_build', { method: 'POST', body: JSON.stringify({ game: custom.value.trim() }) });
    const j = await r.json();
    if (!r.ok) { status.textContent = '✕ ' + (j.error || r.statusText); status.className = 'hint warn'; go.disabled = false; return; }
    poll();
  };
  box.innerHTML = '';
  box.append(h('div', { class: 'panel setup-card' },
    h('h2', {}, t('setup_title')), h('p', {}, t('setup_text')),
    h('h3', {}, st.candidates.length ? t('setup_found') : t('setup_none')), list,
    h('p', { class: 'hint' }, t('setup_custom')), custom,
    h('p', { class: 'hint' }, `${t('setup_where')} ${st.dataDir}`),
    h('div', { class: 'row', style: 'margin-top:10px' }, go, force ? h('button', { class: 'ghost', onclick: () => box.classList.add('hidden') }, '✕') : null),
    status, logBox));
  if (st.running) { go.disabled = true; poll(); }
}
