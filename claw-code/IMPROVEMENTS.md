# vukixAI Agent — Kompletna lista poboljšanja

Verzija 1.0 | April 2026
Analiza trenutnog stanja + šta fali do nivoa Claude Code / Cursor / Codex CLI

---

## 1. PRIKAZ RAZMIŠLJANJA (Thinking Display)

**Trenutno:** Agent ispiše `thinking…` i onda ćuti dok ne završi. Korisnik ne zna šta se dešava.

**Šta fali:**

- **Streaming thinking** — Dok model generiše odgovor sa tool calls (`stream: False`), korisnik ne vidi ništa. Treba ili streamovati narration tekst pre tool calls, ili prikazati animirani "thinking" sa elapsed timerom.
- **Thinking panel sa sadržajem** — Umesto praznog `thinking…`, prikazati šta model razmišlja. Qwen3-Coder podržava `<think>` tagove — parsirati ih i prikazati u collapsible panelu.
- **Elapsed timer** — Dodati `[thinking… 3.2s]` sa live ažuriranjem da korisnik vidi koliko traje.
- **Iteration counter** — Prikazati `[Step 2/10]` kad agent radi multi-step zadatak.

**Implementacija:**
- U `run_agent_loop`: dodati `on_thinking` callback
- U `main.py`: Rich Status sa timerom umesto statičnog `thinking…`
- Parsirati `<think>...</think>` tagove iz Qwen3 output-a i prikazati ih u `[blue]💭 Thinking[/]` panelu

---

## 2. REZIME PROMENA (Change Summary)

**Trenutno:** Agent ili dumpa ceo fajl u chat, ili ne kaže ništa o tome šta je promenio.

**Šta fali:**

- **File change summary** — Posle write_file, prikazati: `✅ src/App.tsx — 3 linije dodato, 1 obrisana`
- **Diff preview** — Za editovane fajlove, prikazati kratak unified diff (5-10 linija max)
- **Session change log** — Na kraju sesije ili na /changes komandu, prikazati sve fajlove koji su izmenjeni
- **Batch summary** — Kad agent menja više fajlova, na kraju prikazati tabelu:
  ```
  Files changed: 3
  ├── src/App.tsx        +15 -3
  ├── src/utils/api.ts   +42 (new file)
  └── package.json       +1 -0
  ```

**Implementacija:**
- Dodati `_write_file_with_diff()` wrapper koji čuva stari sadržaj i generiše diff
- Dodati `state['changes']` list u main.py koji prati sve write/create operacije
- Nova `/changes` slash komanda
- `on_tool_result` za write_file da prikaže kompaktan summary umesto "Wrote X characters"

---

## 3. PROGRESS TRACKING (Plan/Todo Display)

**Trenutno:** Agent nema vizualni plan rada. Korisnik ne zna koliko je koraka ostalo.

**Šta fali:**

- **Live plan display** — Kao Codex CLI `update_plan` — checkbox lista sa statusom:
  ```
  ☑ Read project structure
  ☑ Identify bug in App.tsx
  ☐ Fix handleClick function    ← current
  ☐ Run tests
  ☐ Verify build
  ```
- **Auto-plan iz system prompta** — System prompt traži od modela da generiše plan pre izvršavanja
- **Plan persistence** — Plan se čuva u state i ažurira se kako agent napreduje
- **Step timing** — Koliko je svaki korak trajao

**Implementacija:**
- Dodati `update_plan` tool u TOOLS listu (model ga poziva da kreira/ažurira plan)
- Rich Table sa checkbox renderom u main.py
- `state['plan']` sa listom koraka i statusima

---

## 4. TOOL CALL VIZUALIZACIJA

**Trenutno:** Tool calls se prikazuju sa svim argumentima, uključujući cele file paths i content.

**Šta fali:**

- **Kompaktni tool call prikaz** — Umesto `write_file(path='/very/long/path/to/file.tsx', content='500 lines of code...')`, prikazati: `📝 write_file → src/file.tsx (142 lines)`
- **Collapse dugački content** — Ako je argument duži od 100 karaktera, prikazati samo prvih 50 + `…`
- **Tool call ikone** — Svaki tool ima svoju ikonu:
  - 📂 list_directory
  - 📖 read_file
  - 📝 write_file
  - ⚡ run_command
  - 🔍 find_files / search_in_files
  - 🌐 http_get
  - 💾 save_preference / save_fact
- **Timing per tool** — Koliko je svaki tool call trajao: `📝 write_file → src/App.tsx (0.3s)`
- **Kolapsibilni rezultati** — Tool result preview od max 3-4 linije, sa `[show more]` opcijom (nije moguće u terminalu, ali prikazati prvih 200 karaktera umesto 600)

**Implementacija:**
- Refaktorisati `on_tool_call` da formatira po tipu alata
- Dodati timing u `tool_runner` (start/end)
- Smanjiti result preview sa 600 na 200 karaktera za čistiji output

---

## 5. STREAMING POBOLJŠANJA

**Trenutno:** Tool calling faza je `stream: False` — korisnik čeka bez ikakve indikacije.

**Šta fali:**

- **Streaming tool call faze** — Umesto jednog velikog non-streaming poziva, streamovati i tool-call fazu. Kad model počne da generiše tool call JSON, prikazati `[generating tool call…]`
- **Token counter** — Prikazati koliko tokena je generisano: `[128 tokens, 2.1s]`
- **Speed indicator** — Tokens per second u status baru: `⚡ 23.4 tok/s`

**Implementacija:**
- U agent loop: stream=True za sve pozive, parsirati tool calls iz streama
- Dodati token counting iz Ollama response metadata (`eval_count`, `eval_duration`)
- Prikazati u footer-u nakon svakog odgovora

---

## 6. KONTEKST MENADŽMENT

**Trenutno:** Agent čita fajlove kad mu se kaže, ali ne radi to proaktivno.

**Šta fali:**

- **Auto-context na startu** — Kad se otvori projekat, automatski pročitati: package.json, README.md, tsconfig.json, Cargo.toml — šta god postoji
- **Smart file tree** — Dublja file tree analiza (ne samo top-level) za src/ direktorijum
- **Token budget tracking** — Pratiti koliko tokena je u kontekstu i upozoriti kad se približava limitu
- **Working memory JSON** — Na kraju svakog koraka, agent generiše sažetak stanja:
  ```json
  {
    "project": "moj-raspored",
    "stack": ["HTML", "CSS", "JavaScript"],
    "files_read": ["index.html"],
    "last_action": "read project structure",
    "next_step": "fix drag-and-drop"
  }
  ```
- **Context window indicator** — Prikazati koliko je kontekst popunjen: `[Context: 12k/128k tokens]`

**Implementacija:**
- Pri `/open` automatski čitati ključne config fajlove i dodati u memory
- Dodati `state['working_memory']` JSON koji se ažurira posle svakog tool call-a
- Estimirati token count iz message lengths (4 chars ≈ 1 token)
- Prikazati u prompt-u ili status bar-u

---

## 7. ERROR HANDLING I RECOVERY

**Trenutno:** Kad nešto ne uspe, agent ili stane ili ponavlja isti poziv.

**Šta fali:**

- **Graceful error display** — Umesto raw error teksta, prikazati user-friendly panel:
  ```
  ❌ Command failed: npm install
  Exit code: 1
  Suggestion: Check if Node.js is installed (node --version)
  ```
- **Auto-retry sa kontekstom** — Ako command fails, agent treba automatski da proba alternativu
- **Timeout warnings** — Pre pokretanja dugih komandi, prikazati: `⏳ This may take a while (npm install ~2-5 min)…`
- **Error categorization** — Razlikovati: network error, file not found, permission denied, timeout, syntax error

**Implementacija:**
- Wrapper oko `_run_command` koji kategorizuje greške
- Dodati `known_slow_commands` set za timeout warning
- Rich Panel sa crvenim borderom za greške, žutim za warnings

---

## 8. SESSION UX POBOLJŠANJA

**Trenutno:** Osnovni chat loop sa `/help` komandama.

**Šta fali:**

- **Welcome screen sa projektom info** — Kad se uđe u chat, prikazati summary projekta:
  ```
  📁 Project: moj-raspored
  📦 Stack: HTML/CSS/JS (vanilla)
  📝 Files: 1 (index.html, 19KB)
  💾 Memory: 5 turns, 2 prefs, 3 facts
  🤖 Model: qwen3-coder:30b (temp: 0.15)
  ```
- **Status bar** — Persistent footer sa: model, cwd, token count, session duration
- **Command history navigation** — Strelice gore/dole za prethodne komande
- **Auto-complete za file paths** — Kad korisnik kuca `@`, prikazati listu fajlova
- **Multi-line input** — Podrška za paste-ovanje više linija koda
- **Colored output po tipu** — Razlikovati: agent tekst (belo), tool calls (žuto), results (zeleno), errors (crveno), thinking (plavo)
- **Session timer** — Koliko sesija traje + koliko API poziva je napravljeno
- **Cost estimator** — Za lokalni rad nije relevantan $, ali prikazati: `Tokens used: 45.2k in/12.8k out`

**Implementacija:**
- Proširiti startup banner u main.py sa više informacija
- Dodati `state['session_start']`, `state['api_calls']`, `state['tokens']` tracking
- Token tracking iz Ollama response: `eval_count`, `prompt_eval_count`

---

## 9. NOVI ALATI (Tools)

**Trenutno:** 12 alata. Dovoljno za osnovno, ali fali ključnih.

**Šta fali:**

- **edit_file** — Umesto write_file koji piše ceo fajl, dodati alat koji radi patch/diff edit (zameni specifičnu sekciju). Ovo je #1 prioritet jer sprečava gubitak koda.
- **apply_patch** — Codex CLI stil patch format za precizne izmene
- **undo_last_write** — Vraća poslednji write_file (čuva backup pre pisanja)
- **tree** — Rekurzivni file tree (ne samo top-level list_directory)
- **ask_user** — Agent eksplicitno pita korisnika pitanje i čeka odgovor (umesto da halucinira)
- **update_plan** — Tool za kreiranje i ažuriranje plana rada (vidljiv korisniku)
- **count_tokens** — Estimacija koliko tokena je u kontekstu

**Implementacija:**
- `edit_file(path, old_text, new_text)` — find-and-replace u fajlu
- `apply_patch(patch_text)` — parsira Codex-stil patch format
- Dodati backup sistem: pre svakog write_file, sačuvati `.backup` kopiju
- `tree(path, depth=3)` — rekurzivni listing sa depth limitom

---

## 10. KONFIGURISANJE I SETTINGS

**Trenutno:** Hardkodirane vrednosti u kodu. Temperatura, model, max_iterations.

**Šta fali:**

- **Config fajl** — `.vukixai.json` u projektu ili `~/.vukixai/config.json` globalno:
  ```json
  {
    "model": "qwen3-coder:30b",
    "temperature": 0.15,
    "max_iterations": 15,
    "auto_verify": true,
    "show_thinking": true,
    "result_preview_length": 200,
    "theme": "dark"
  }
  ```
- **Runtime config commands** — `/set temperature 0.2`, `/set max_iterations 20`
- **Per-project config** — Različiti settings za različite projekte
- **AGENTS.md / CLAW.md podrška** — Čitati projektne instrukcije iz markdown fajla u root-u

**Implementacija:**
- Novi `config.py` modul sa load/save/merge logikom
- Slash komande `/set` i `/config`
- Na `/open` čitati `.vukixai.json` ako postoji

---

## 11. VERIFIKACIJA I AUTO-TEST

**Trenutno:** Agent ne proverava svoj rad automatski.

**Šta fali:**

- **Auto-verify posle write** — Posle pisanja .py fajla, automatski pokrenuti `python -c "import ast; ast.parse(open('file').read())"` za syntax check
- **Auto-build check** — Ako postoji package.json, posle izmena pokrenuti `npm run build` ili `tsc --noEmit`
- **Auto-lint** — Ako postoji .eslintrc ili ruff.toml, pokrenuti linter
- **Test runner detection** — Detektovati test framework (pytest, jest, mocha) i predložiti pokretanje testova
- **Verification status** — Na kraju rada prikazati:
  ```
  ✅ Syntax check: passed
  ✅ Build: passed
  ⚠️ Tests: not run (no test file found)
  ```

**Implementacija:**
- Dodati `verify_file(path)` funkciju koja detektuje tip i pokreće odgovarajući check
- Dodati u system prompt instrukciju da agent MORA pokrenuti verifikaciju
- Post-write hook u `_write_file` koji automatski verifikuje

---

## 12. GIT INTEGRACIJA

**Trenutno:** Samo `git_status` tool sa basic status/log/diff.

**Šta fali:**

- **Auto-commit suggestion** — Posle skupa izmena, predložiti commit sa generisanom porukom
- **Branch awareness** — Prikazati trenutni branch u promptu
- **Diff before commit** — Prikazati šta će biti uključeno u commit
- **Git blame integration** — Kad agent čita fajl, može da vidi ko je zadnji menjao svaku liniju
- **Stash support** — `/stash` i `/stash pop` komande

**Implementacija:**
- Proširiti `git_status` tool sa `commit`, `branch`, `stash` modovima
- Dodati branch u prompt: `main You>`
- Nova `/commit` slash komanda sa auto-generisanom porukom

---

## PRIORITETI

### P0 — Danas (30 min)
1. ✅ Novi system prompt (URAĐENO)
2. ✅ Temperature 0.15 (URAĐENO)
3. ✅ Brža loop detekcija (URAĐENO)
4. ✅ Default model qwen3-coder:30b (URAĐENO)

### P1 — URAĐENO
5. ✅ Thinking display sa elapsed timerom
6. ✅ Kompaktni tool call prikaz (ikone + timing)
7. ✅ File change summary (diff preview)
8. ✅ `edit_file` tool (find-and-replace umesto full write)
9. ✅ Token/speed tracking iz Ollama metadata

### P2 — URAĐENO
10. ✅ `update_plan` tool sa checkbox renderom
11. ✅ `tree` tool (rekurzivni file listing)
12. ✅ Config fajl sistem (.vukixai.json)
13. ✅ Auto-verify posle write_file (Python, JSON, HTML, JS/TS)
14. ✅ Session timer i API call counter (/stats)
15. ✅ Smanjiti tool result preview na 200 chars / 4 linije

### P3 — URAĐENO
16. ✅ Working memory JSON (auto-tracks files_read, last_action, tool_calls)
17. ✅ `apply_patch` tool (Codex-stil multi-file patch format)
18. ✅ `undo_last_write` sa backup sistemom (.bak + .redo)
19. ✅ Git branch u promptu + `/commit` + `/diff` komande
20. ✅ Token estimate u status liniji posle svakog odgovora
21. ✅ `/tokens` komanda (context window usage)
22. ✅ `/changes` komanda (session change log) — urađeno u P1
