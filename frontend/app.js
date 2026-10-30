"use strict";

// Одностраничный интерфейс Must Play: роутинг по хешу, все данные — через REST API.

const view = document.getElementById("view");
const errorBox = document.getElementById("error");
const PAGE_SIZE = 20;

// ---------- общие помощники ----------

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function fmt(value, digits = 1) {
  return value === null || value === undefined ? "—" : Number(value).toFixed(digits);
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

// Ошибки API приходят в едином формате {"error": {"code", "message", "details"}}
function describeError(body, status) {
  const error = body && body.error;
  if (!error) return `Ошибка ${status}`;
  let text = error.message;
  if (Array.isArray(error.details)) {
    text += ": " + error.details.map((d) => `${(d.loc || []).slice(1).join(".")} — ${d.msg}`).join("; ");
  } else if (error.details && typeof error.details === "string") {
    text += ` (${error.details})`;
  }
  return text;
}

async function api(path, options = {}) {
  const init = { ...options, headers: { ...(options.headers || {}) } };
  if (init.body && typeof init.body !== "string") {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(init.body);
  }
  let response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error("Сервер недоступен");
  }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(describeError(body, response.status));
  return body;
}

function query(params) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v !== null && v !== undefined) q.set(k, v);
  });
  return q.toString();
}

function divergenceBadge(score) {
  if (!score || !score.divergence) return "";
  return score.divergence === "overrated"
    ? '<span class="badge over">пресса перехвалила</span>'
    : '<span class="badge under">пресса недооценила</span>';
}

function year(game) {
  return game.release_date ? game.release_date.slice(0, 4) : "—";
}

function gameCards(games, extra = () => "") {
  if (!games.length) return '<p class="muted">Ничего не найдено.</p>';
  return `<div class="cards">${games
    .map(
      (g) => `<a class="card" href="#/game/${g.app_id}">
        <img src="${esc(g.header_image || "")}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
        <div><b>${esc(g.name)}</b><br>
        <span class="muted">${year(g)} · индекс ${fmt(g.score && g.score.index_score)}</span>${extra(g)}</div>
      </a>`
    )
    .join("")}</div>`;
}

function pager(total, offset, onPage) {
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const wrap = document.createElement("div");
  wrap.className = "pager";
  wrap.innerHTML = `<button class="secondary" ${page <= 1 ? "disabled" : ""}>← Назад</button>
    <span class="muted">Страница ${page} из ${pages} · всего ${total}</span>
    <button class="secondary" ${page >= pages ? "disabled" : ""}>Вперёд →</button>`;
  const [prev, , next] = wrap.children;
  prev.onclick = () => onPage(offset - PAGE_SIZE);
  next.onclick = () => onPage(offset + PAGE_SIZE);
  return wrap;
}

async function genreOptions(selected = "") {
  const genres = await api("/genres");
  return '<option value="">Все жанры</option>' + genres.map((g) => `<option ${g.name === selected ? "selected" : ""}>${esc(g.name)}</option>`).join("");
}

// ---------- страницы ----------

async function ratingPage() {
  view.innerHTML = `<h1>Рейтинг всех времён</h1>
    <p class="muted">Индекс = 0,4 × пресса (с поправкой на щедрость) + 0,6 × игроки (нижняя граница Уилсона). В рейтинге игры с 50+ голосами.</p>
    <form class="filters" id="f">
      <label>Жанр <select name="genre">${await genreOptions()}</select></label>
      <label>Десятилетие <select name="decade"><option value="">Все</option>${[1990, 2000, 2010, 2020].map((d) => `<option value="${d}">${d}-е</option>`).join("")}</select></label>
      <button>Показать</button>
    </form>
    <div id="list"></div>`;
  const form = document.getElementById("f");
  const load = async (offset = 0) => {
    const data = Object.fromEntries(new FormData(form));
    const page = await api(`/rating?${query({ ...data, limit: PAGE_SIZE, offset })}`);
    const list = document.getElementById("list");
    list.innerHTML = `<table><thead><tr><th class="num">#</th><th>Игра</th><th>Год</th>
      <th class="num">Индекс</th><th class="num">Игроки</th><th class="num">Пресса</th><th></th></tr></thead><tbody>
      ${page.items
        .map(
          (g, i) => `<tr><td class="num">${offset + i + 1}</td>
          <td><a href="#/game/${g.app_id}">${esc(g.name)}</a></td><td>${year(g)}</td>
          <td class="num"><b>${fmt(g.score.index_score)}</b></td><td class="num">${fmt(g.score.player_score)}</td>
          <td class="num">${fmt(g.score.critic_score, 0)}</td><td>${divergenceBadge(g.score)}</td></tr>`
        )
        .join("")}</tbody></table>`;
    list.append(pager(page.total, offset, (o) => load(o).catch((e) => showError(e.message))));
  };
  form.onsubmit = (e) => {
    e.preventDefault();
    clearError();
    load().catch((err) => showError(err.message));
  };
  await load();
}

async function mustPlayPage() {
  view.innerHTML = `<h1>Must play</h1>
    <p class="muted">Игра попадает в список, если индекс два пересчёта подряд держится высоко: вход от 95, выход ниже 93.</p>
    <div id="list"></div>`;
  const load = async (offset = 0) => {
    const page = await api(`/must-play?${query({ limit: PAGE_SIZE, offset })}`);
    const list = document.getElementById("list");
    list.innerHTML = gameCards(page.items);
    list.append(pager(page.total, offset, (o) => load(o).catch((e) => showError(e.message))));
  };
  await load();
}

async function gamePage(id) {
  const [game, similar] = await Promise.all([api(`/games/${id}`), api(`/games/${id}/similar`)]);
  const s = game.score || {};
  const chips = (items) => items.map((x) => `<span class="badge">${esc(x.name)}</span>`).join(" ") || '<span class="muted">—</span>';
  const statusText = { in_list: "в списке must play", candidate: "кандидат в must play", dropped: "выбыла из must play" };
  view.innerHTML = `<div class="game-head">
      ${game.header_image ? `<img src="${esc(game.header_image)}" alt="">` : ""}
      <div><h1>${esc(game.name)}</h1>
        <p class="muted">${year(game)} · ${game.is_free ? "бесплатно" : game.price ? `$${game.price}` : "цена неизвестна"}
          · ${["windows", "mac", "linux"].filter((p) => game[p]).join(", ") || "платформы неизвестны"}</p>
        <p>${esc(game.short_description || "")}</p>
        <p>${game.must_play_status ? `<span class="badge">${statusText[game.must_play_status]}</span>` : ""} ${divergenceBadge(s)}</p>
        <p><a href="#/edit/${game.app_id}">Редактировать</a> · <a href="#" id="del">Удалить</a></p>
      </div></div>
    <div class="scores">
      <div class="score"><span class="muted">Индекс</span><b>${fmt(s.index_score)}</b>${s.is_eligible ? "" : '<span class="muted">мало голосов</span>'}</div>
      <div class="score"><span class="muted">Игроки (Уилсон)</span><b>${fmt(s.player_score)}</b><span class="muted">${game.positive} 👍 / ${game.negative} 👎</span></div>
      <div class="score"><span class="muted">Пресса</span><b>${fmt(s.critic_score, 0)}</b><span class="muted">обзоров с оценкой: ${s.critic_reviews_count ?? 0}</span></div>
    </div>
    <h2>Жанры и теги</h2><p class="chips">${chips(game.genres)}</p><p class="chips">${chips(game.tags.slice(0, 15))}</p>
    <h2>Что пишет пресса</h2>
    ${game.reviews.length ? game.reviews.map((r) => `<div class="quote">${esc(r.quote) || '<span class="muted">без цитаты</span>'}<br>
      <span class="muted">${esc(r.outlet || "издание не указано")}${r.raw_score ? ` · ${esc(r.raw_score)} → ${r.score}` : ""}</span></div>`).join("") : '<p class="muted">Обзоров нет.</p>'}
    <h2>Похожие игры</h2>${gameCards(similar, (g) => `<br><span class="muted">близость ${fmt(g.similarity, 2)}</span>`)}`;
  document.getElementById("del").onclick = async (e) => {
    e.preventDefault();
    if (!confirm(`Удалить «${game.name}» из каталога?`)) return;
    try {
      await api(`/games/${id}`, { method: "DELETE" });
      location.hash = "#/catalog";
    } catch (err) {
      showError(err.message);
    }
  };
}

async function pickPage() {
  view.innerHTML = `<h1>Во что поиграть</h1>
    <form class="form" id="f">
      <label>Жанр <select name="genre">${await genreOptions()}</select></label>
      <label>Тег <input name="tag" placeholder="например, Roguelike"></label>
      <label>Режим <select name="mode"><option value="">Любой</option><option value="single">Одиночная</option>
        <option value="coop">Кооператив</option><option value="multiplayer">Мультиплеер</option></select></label>
      <label>Платформа <select name="platform"><option value="">Любая</option><option value="windows">Windows</option>
        <option value="mac">Mac</option><option value="linux">Linux</option></select></label>
      <label>Язык <input name="language" placeholder="например, Russian"></label>
      <label>Цена до, $ <input name="max_price" type="number" min="0" step="1"></label>
      <div class="actions"><button>Подобрать</button></div>
    </form>
    <div id="result"></div>`;
  document.getElementById("f").onsubmit = async (e) => {
    e.preventDefault();
    clearError();
    const d = Object.fromEntries(new FormData(e.target));
    const body = {
      genres: d.genre ? [d.genre] : [],
      tags: d.tag ? [d.tag.trim()] : [],
      mode: d.mode || null,
      platform: d.platform || null,
      language: d.language.trim() || null,
      max_price: d.max_price || null,
      limit: 12,
    };
    try {
      const games = await api("/recommendations", { method: "POST", body });
      document.getElementById("result").innerHTML = `<h2>Подборка</h2>${gameCards(games)}`;
    } catch (err) {
      showError(err.message);
    }
  };
}

function bars(rows, label, value, max, digits = 1) {
  return `<div class="bars">${rows
    .map((r) => `<div class="bar"><span>${esc(label(r))}</span><span class="fill" style="width:${(value(r) / max) * 100}%"></span><span>${fmt(value(r), digits)}</span></div>`)
    .join("")}</div>`;
}

async function analyticsPage() {
  const [genres, years, over, under, strict, generous, runs] = await Promise.all([
    api("/analytics/genres?min_games=300"),
    api("/analytics/releases?year_from=2006&year_to=2025"),
    api("/analytics/divergence?kind=overrated&limit=5"),
    api("/analytics/divergence?kind=underrated&limit=5"),
    api("/analytics/outlets?order=strict&limit=5"),
    api("/analytics/outlets?order=generous&limit=5"),
    api("/rating/runs?limit=3"),
  ]);
  const divergenceTable = (rows) => `<table><thead><tr><th>Игра</th><th class="num">Пресса</th><th class="num">Игроки, %</th><th class="num">Разница</th></tr></thead><tbody>
    ${rows.map((r) => `<tr><td><a href="#/game/${r.app_id}">${esc(r.name)}</a></td><td class="num">${fmt(r.critic_score, 0)}</td><td class="num">${fmt(r.positive_share)}</td><td class="num">${fmt(r.gap)}</td></tr>`).join("")}</tbody></table>`;
  const outletTable = (rows) => `<table><thead><tr><th>Издание</th><th class="num">Обзоров</th><th class="num">Средняя</th><th class="num">От среднего</th></tr></thead><tbody>
    ${rows.map((r) => `<tr><td>${esc(r.outlet)}</td><td class="num">${r.reviews}</td><td class="num">${fmt(r.avg_score)}</td><td class="num">${fmt(r.vs_average)}</td></tr>`).join("")}</tbody></table>`;
  const maxReleases = Math.max(...years.map((y) => y.releases));
  view.innerHTML = `<h1>Аналитика</h1>
    <div class="notice">Последний пересчёт рейтинга: ${runs.length ? `#${runs[0].id}, ${runs[0].status}, игр ${runs[0].games_scored}` : "ещё не было"}.
      <button id="recalc">Пересчитать рейтинг</button> <span id="recalc-status" class="muted"></span></div>
    <h2>Средний индекс по жанрам</h2>${bars(genres, (g) => `${g.genre} (${g.games})`, (g) => g.avg_index, 100)}
    <h2>Релизы по годам</h2>${bars(years, (y) => `${y.year} · бесплатных ${fmt(y.free_share)}%`, (y) => y.releases, maxReleases, 0)}
    <h2>Пресса перехвалила</h2>${divergenceTable(over)}
    <h2>Пресса недооценила</h2>${divergenceTable(under)}
    <h2>Самые строгие издания</h2>${outletTable(strict)}
    <h2>Самые щедрые издания</h2>${outletTable(generous)}`;
  document.getElementById("recalc").onclick = async (e) => {
    const button = e.target;
    const status = document.getElementById("recalc-status");
    button.disabled = true;
    status.textContent = "Пересчёт идёт, это около 20 секунд…";
    try {
      const run = await api("/rating/recalculate", { method: "POST" });
      status.textContent = `Готово: пересчёт #${run.id}, игр ${run.games_scored}.`;
    } catch (err) {
      status.textContent = "";
      showError(err.message);
    } finally {
      button.disabled = false;
    }
  };
}

async function catalogPage() {
  view.innerHTML = `<h1>Каталог</h1>
    <form class="filters" id="f">
      <label>Название <input name="q" placeholder="поиск"></label>
      <label>Сортировка <select name="sort"><option value="votes">по голосам</option><option value="name">по названию</option>
        <option value="release_date">по дате</option><option value="price">по цене</option></select></label>
      <button>Найти</button> <a href="#/new">+ Добавить игру</a>
    </form>
    <div id="list"></div>`;
  const form = document.getElementById("f");
  const load = async (offset = 0) => {
    const data = Object.fromEntries(new FormData(form));
    const page = await api(`/games?${query({ ...data, desc: data.sort !== "name", limit: PAGE_SIZE, offset })}`);
    const list = document.getElementById("list");
    list.innerHTML = `<table><thead><tr><th>app_id</th><th>Игра</th><th>Год</th><th class="num">Цена</th><th class="num">Голосов</th><th></th></tr></thead><tbody>
      ${page.items
        .map(
          (g) => `<tr><td>${g.app_id}</td><td><a href="#/game/${g.app_id}">${esc(g.name)}</a></td><td>${year(g)}</td>
          <td class="num">${g.is_free ? "free" : fmt(g.price, 2)}</td><td class="num">${g.positive + g.negative}</td>
          <td><a href="#/edit/${g.app_id}">изменить</a></td></tr>`
        )
        .join("")}</tbody></table>`;
    list.append(pager(page.total, offset, (o) => load(o).catch((e) => showError(e.message))));
  };
  form.onsubmit = (e) => {
    e.preventDefault();
    clearError();
    load().catch((err) => showError(err.message));
  };
  await load();
}

async function editPage(id) {
  const game = id ? await api(`/games/${id}`) : null;
  view.innerHTML = `<h1>${game ? `Изменить: ${esc(game.name)}` : "Новая игра"}</h1>
    <form class="form" id="f" novalidate>
      ${game ? "" : '<label>app_id <input name="app_id" type="number" required></label>'}
      <label>Название <input name="name" value="${esc(game ? game.name : "")}"></label>
      <label>Дата выхода <input name="release_date" type="date" value="${game && game.release_date ? game.release_date : ""}"></label>
      <label>Цена, $ <input name="price" type="number" step="0.01" value="${game && game.price !== null ? game.price : ""}"></label>
      <label>Жанры через запятую <input name="genres" value="${esc(game ? game.genres.map((g) => g.name).join(", ") : "")}"></label>
      <label class="wide">Описание <textarea name="short_description" rows="3">${esc(game ? game.short_description || "" : "")}</textarea></label>
      <div class="actions"><button>Сохранить</button><a href="${game ? `#/game/${id}` : "#/catalog"}">Отмена</a></div>
    </form>`;
  document.getElementById("f").onsubmit = async (e) => {
    e.preventDefault();
    clearError();
    const d = Object.fromEntries(new FormData(e.target));
    const body = {
      name: d.name,
      release_date: d.release_date || null,
      price: d.price === "" ? null : d.price,
      short_description: d.short_description || null,
      genres: d.genres.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      const saved = game
        ? await api(`/games/${id}`, { method: "PATCH", body })
        : await api("/games", { method: "POST", body: { ...body, app_id: Number(d.app_id) || d.app_id } });
      location.hash = `#/game/${saved.app_id}`;
    } catch (err) {
      showError(err.message);
    }
  };
}

// ---------- роутинг ----------

const routes = [
  [/^#\/rating$/, ratingPage],
  [/^#\/must-play$/, mustPlayPage],
  [/^#\/game\/(\d+)$/, gamePage],
  [/^#\/pick$/, pickPage],
  [/^#\/analytics$/, analyticsPage],
  [/^#\/catalog$/, catalogPage],
  [/^#\/new$/, () => editPage(null)],
  [/^#\/edit\/(\d+)$/, editPage],
];

async function render() {
  const hash = location.hash || "#/rating";
  clearError();
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", hash.startsWith(`#/${a.dataset.nav}`)));
  const route = routes.find(([re]) => re.test(hash));
  if (!route) {
    location.hash = "#/rating";
    return;
  }
  view.innerHTML = '<p class="muted">Загрузка…</p>';
  try {
    await route[1](...hash.match(route[0]).slice(1));
  } catch (err) {
    view.innerHTML = "";
    showError(err.message);
  }
}

window.addEventListener("hashchange", render);
render();
