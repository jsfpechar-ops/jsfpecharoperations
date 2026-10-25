# 0390: Leon offers situation chips answered from the guide (no AI call)

Status: todo
Depends on: 0389 (same branch, not merged) | Branch: claude/0387-leon-chat-look (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25): "Leon should also have expected topics like Havel so we save AI costs", and: "Wi-Fi and really obvious stuff is available on the Airbnb booking; think of a situation when they would need it really." Under Leon's welcome bubble, the chat shows **situation chips**: the moments when a guest needs help on the spot. Each chip maps to built-in card kinds. A chip shows only when at least one matching card is on the page. Everything happens in the browser from the cards already rendered there. There is no request, no AI call, nothing stored and nothing counted.

| situation key | card kinds (in this order) |
|---|---|
| cant_get_in | keys, checkin |
| cold | heating, hot_water, air_conditioning |
| broken | something_wrong |
| parking | parking, garage |
| trash | trash |
| checkout | checkout |
| emergency | emergency |

1. Tap a chip. Its label shows as the guest's bubble. Leon then answers with ONE bubble per matching card, at most 2 cards, in the order above. Each bubble holds the card title, its facts line, its "Where:" line, its numbered steps and its "Watch out:" line, as plain text copied from the card, then a link `leon_see_card` that scrolls to that card (photos and video stay on the card).
2. After the answer, the situation chips appear again so the guest can keep going. Typing a question still goes to Leon as before.

## 2. Context

- `App/app/templates/guest/guide.html`: `{% for group in groups %}<p class="g-question-kicker" data-guide-topic>{{ group.title }}</p>{% for card in group.cards %}<div class="g-card g-guide-card" data-guide-card="{{ card.id }}"><h2>{{ card.title }}</h2>` and so on: an optional `<p>` with facts (direct child, no class), `p.g-guide-where`, `ol.g-guide-steps > li`, `div.g-guide-warn`, then photos, video and `details.g-guide-original` (skip these three). `_leon.html` is included after the loop.
- `App/app/static/guest-leon.js` after 0389: `bubble(role, kind, body)` sets text with `textContent` only. Keep that: never use innerHTML with card text. `welcome()` draws the fixed first bubble, and `render(data)` empties the log and calls `welcome()` first.
- Guest CSS: `App/app/static/guest.css`, 0387 block `.g-leon-*`.
- Copy: `App/app/i18n.py` (en, cs, de, es, fr) and `App/app/guest_uk_i18n.py` (uk).

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/guest/guide.html | card id and kind attribute |
| App/app/static/guest-leon.js | chips and local answers |
| App/app/static/guest.css | append chip rules |
| App/app/i18n.py, App/app/guest_uk_i18n.py | 8 new keys |
| App/app/templates/guest/_leon.html | 1 data attribute, hidden situation list |
| App/app/templates/guest/base.html | bump guest.css and guest-leon.js keys to `20261025-0390` |
| App/tests/static_versions.json | `--write` |
| App/tests/test_guest_leon_browser.py | new test |

## 4. Steps

1. **Template** (`guide.html`): on each card div add `id="card-{{ card.id }}" data-guide-kind="{{ card.kind }}"`. If `card.kind` is not in the card dict the view passes (check `routes/guest_guide_view.py` ~83, it has `"kind"`), STOP and report.

2. **Copy**: add after `leon_welcome` in each language: `leon_see_card` and seven chip labels `leon_sit_<key>`.

| key | en | cs | de | es | fr | uk |
|---|---|---|---|---|---|---|
| leon_see_card | See the card with photos | Zobrazit kartu s fotkami | Karte mit Fotos ansehen | Ver la ficha con fotos | Voir la fiche avec photos | Переглянути картку з фото |
| leon_sit_cant_get_in | I can't get in | Nemůžu se dostat dovnitř | Ich komme nicht rein | No puedo entrar | Je n'arrive pas à entrer | Не можу потрапити всередину |
| leon_sit_cold | It's cold / no hot water | Je zima / neteče teplá voda | Es ist kalt / kein Warmwasser | Hace frío / no hay agua caliente | Il fait froid / pas d'eau chaude | Холодно / немає гарячої води |
| leon_sit_broken | Something isn't working | Něco nefunguje | Etwas funktioniert nicht | Algo no funciona | Quelque chose ne marche pas | Щось не працює |
| leon_sit_parking | Where do I park? | Kde zaparkuju? | Wo kann ich parken? | ¿Dónde aparco? | Où me garer ? | Де припаркуватися? |
| leon_sit_trash | Rubbish and recycling | Odpadky a třídění | Müll und Recycling | Basura y reciclaje | Poubelles et tri | Сміття і сортування |
| leon_sit_checkout | Checking out | Odjezd | Check-out | Salida | Départ | Виїзд |
| leon_sit_emergency | Emergency | Nouzová situace | Notfall | Emergencia | Urgence | Надзвичайна ситуація |

3. **`_leon.html`**: on the root section add `data-text-see-card="{{ t('leon_see_card') }}"`. Inside the section, right before the log div, add one hidden list the script reads (labels stay in the template, not the JS):
```html
  <ul hidden data-leon-situations>
    {% for key, kinds in [("cant_get_in", "keys checkin"), ("cold", "heating hot_water air_conditioning"), ("broken", "something_wrong"), ("parking", "parking garage"), ("trash", "trash"), ("checkout", "checkout"), ("emergency", "emergency")] %}
    <li data-key="{{ key }}" data-kinds="{{ kinds }}">{{ t('leon_sit_' ~ key) }}</li>
    {% endfor %}
  </ul>
```

4. **JS** (`guest-leon.js`). Add after `welcome()`:
```js
  // 0390: the guide's own topics as chips. Answers are copied from the cards on this page:
  // no request, no AI call, nothing stored or counted. Text only (textContent), never HTML.
  var local = []; // nodes of chip exchanges, kept across render()
  function topics() {
    var lis = root.querySelectorAll("[data-leon-situations] li");
    return Array.prototype.map.call(lis, function (li) {
      var cards = [];
      li.getAttribute("data-kinds").split(" ").forEach(function (k) {
        Array.prototype.forEach.call(document.querySelectorAll('[data-guide-kind="' + k + '"]'), function (c) { if (cards.length < 2 && cardText(c)) cards.push(c); });
      });
      return { title: li.textContent.trim(), cards: cards };
    }).filter(function (tp) { return tp.cards.length; });
  }
  function chips(items, onPick, label) {
    var wrap = document.createElement("div");
    wrap.className = "g-leon-chips";
    wrap.setAttribute("role", "group");
    if (label) wrap.setAttribute("aria-label", label);
    items.forEach(function (it) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "g-leon-chip";
      b.textContent = it.title;
      b.addEventListener("click", function () { onPick(it); });
      wrap.appendChild(b);
    });
    log.appendChild(wrap);
    return wrap;
  }
  function cardTitle(card) { var h = card.querySelector("h2"); return h ? h.textContent.trim() : ""; }
  function cardText(card) {
    var lines = [];
    Array.prototype.forEach.call(card.children, function (el) {
      if (el.tagName === "P" && !el.className) lines.push(el.textContent.trim());
      else if (el.classList.contains("g-guide-where")) lines.push(el.textContent.trim().replace(/\s+/g, " "));
      else if (el.classList.contains("g-guide-steps")) Array.prototype.forEach.call(el.querySelectorAll("li"), function (li, i) { lines.push((i + 1) + ". " + li.textContent.trim()); });
      else if (el.classList.contains("g-guide-warn")) lines.push(el.textContent.trim().replace(/\s+/g, " "));
    });
    return lines.filter(Boolean).join("\n");
  }
  function keep(node) { local.push(node); return node; }
  function answerSituation(tp) {
    keep(bubble("guest", "", tp.title));
    var last = null;
    tp.cards.forEach(function (card) {
      var node = keep(bubble("leon", "", cardTitle(card) + "\n" + cardText(card)));
      node.setAttribute("data-leon-msg", "card");
      var a = document.createElement("a");
      a.className = "g-leon-see";
      a.href = "#" + card.id;
      a.textContent = text("text-see-card");
      node.appendChild(a);
      last = node;
    });
    keep(topicChips());
    if (last && last.scrollIntoView) last.scrollIntoView({ block: "nearest" });
  }
  function topicChips() {
    return chips(topics(), answerSituation, "");
  }
```
   - `bubble()` builds its own node and appends it to `log`. The welcome chips must come right after the welcome. Change `welcome()` to call `topicChips()` after the bubble, but only when `topics().length > 0`, and mark that chip group with `wrap.setAttribute("data-leon-welcome-chips", "")`. Drop older welcome chips: once any card has been answered, only the newest topic-chip group stays clickable. In `answerSituation`, before adding new items, remove every `.g-leon-chips` element already in `log` except the welcome one (remove them from `local` too).
   - In `render(data)`, after `welcome();` and before the server messages, re-append the `local` nodes in order (`local.forEach(function (n) { log.appendChild(n); })`), so a later typed question does not wipe the chip conversation.
   - The `bubble()` Leon text uses `white-space: pre-line` (0352 CSS), so the `\n` lines show as lines.

5. **CSS** (append to guest.css):
```css
/* 0390: guide topics as chips under Leon's bubbles. */
.g-leon-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 2px 0 4px; }
.g-leon-chip { min-height: 44px; padding: 8px 16px; border: 1px solid var(--g-accent-soft); border-radius: var(--g-pill); background: var(--g-surface); color: var(--g-accent); font: inherit; font-size: 15px; font-weight: 600; text-align: left; cursor: pointer; }
.g-leon-chip:hover { background: var(--g-accent-soft); }
.g-leon-chip:focus-visible { outline: 2px solid var(--g-accent); outline-offset: 2px; }
.g-leon-see { display: inline-block; margin-top: 8px; color: var(--g-accent); font-size: 14.5px; font-weight: 600; }
```
   If `--g-accent-soft` makes the border invisible in the screenshot, use `var(--g-line)` for the border instead.

6. **Version keys**: bump guest.css and guest-leon.js in `templates/guest/base.html` to `?v=20261025-0390`, then `tests/test_static_versions.py --write`.

7. **Test** `test_leon_topic_chips` in `test_guest_leon_browser.py`: seed like the existing phone test, en, 390x844. Before any action, count the page's network requests to the Leon URL (`page.on("request", ...)`, keeping requests whose URL contains the leon url path). Then check:
   - Look at the seed (`_seed()` in that file) to see which card kinds it creates and give them steps if needed so that at least "cant_get_in", "checkout" and "emergency" have a filled card. Assert there is no chip whose text is "Wi-Fi", and the `[data-leon-welcome-chips] .g-leon-chip` count equals the number of situations with a filled card.
   - Tap "I can't get in". A `.g-leon-msg--guest` shows "I can't get in", and a `[data-leon-msg=card]` bubble contains the keys or check-in card's first step, with a link to `#card-<id>`.
   - No new request went to the Leon URL during the taps (the count is unchanged).
   - Sending "Hello" (local reply) keeps the card bubble on screen.
   - `document.documentElement.scrollWidth <= 390`.
   - Save `#leon` screenshots `leon-chips-390.png` (before tapping) and `leon-card-answer-390.png` (after) to SHOTS and to `docs/tasks/screenshots-0387/`.

## 5. Do not touch

leon.py, routes, caps, the prompt, stored history. Card markup other than the two attributes and the id.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
node --check app/static/guest-leon.js
UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_guest_leon_browser.py tests/test_guest_leon_chat.py tests/test_leon.py tests/test_guest_guide_browser.py tests/test_guide_browser.py tests/test_guest_browser_e2e.py tests/test_static_versions.py -q --tb=short -rs 2>&1 | tail -30
cd .. && git checkout -- $(git ls-files -m docs/tasks | grep screenshots- | grep -v screenshots-0387) 2>/dev/null; true
```
If a test fails, put its first assertion line in the report. Fix only inside §3.

## 7. Acceptance

- [ ] §6 passes, 0 skipped.
- [ ] Both screenshots exist and you looked at each once: chips under the welcome, then a card answer with the link and the chips again.

## 9. Report

No report file. ONE commit `0390: Leon offers situation chips from the guide`, including this brief and the screenshots, ending with the Haiku Co-Authored-By trailer and `Claude-Session: https://claude.ai/code/session_01Lvzax2VbKkYR4rb7JYLc3K`. Do not push.
