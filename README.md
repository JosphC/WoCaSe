# WoCaSe — Estimator de Timp de Execuție Worst-Case

<p align="center">
  <strong>Instrument automatizat pentru estimarea timpului de execuție worst-case al DEM MainFunction</strong><br>
  <em>Instrumentare · Compilare · Extragere · Simulare · Raportare</em>
</p>

---

## Descriere generală

**WoCaSe** este o aplicație desktop care automatizează fluxul complet de estimare a timpului de execuție în cel mai defavorabil caz (Worst-Case Execution Time / WCET) pentru funcția `Icsp_Dem_MainFunction()`, în cadrul proiectelor AUTOSAR pentru unități de control electronic (ECU) auto, construite cu lanțul de instrumente **TD5**.

În loc de măsurători pe bancul de probă (bench), consumatoare de timp, pentru fiecare variantă de proiect, WoCaSe folosește un **model analitic de simulare bazat pe micro-costuri** pentru a estima timpul de execuție pe trei scenarii standardizate de tip worst-case și șase configurații de calibrare — reducând timpul de validare de la zile la minute.

### Funcționalități principale

| Etapă | Descriere |
|-------|-----------|
| **Instrumentare** | Modifică automat fișierele sursă C și fișierele de configurare (ARXML, CBD, TDCL, XML) pentru a injecta cod de măsurare a timpului de execuție bazat pe GPT |
| **Compilare** | Apelează TD5 CLI pentru a importa și compila proiectul instrumentat |
| **Extragere** | Analizează fișierele generate `icsp_dem_cnf.c` și fișierele header PTU pentru a extrage dinamic toți parametrii de configurare DEM |
| **Simulare** | Rulează modelul analitic pas cu pas pe 3 scenarii × 6 calibrări, cu analiză opțională Monte Carlo a timpului de vârf |
| **Raportare** | Generează un raport Excel complet, cu tabele colorate condiționat, grafice, analiză de sensibilitate și comparații între variante |

### Funcționalități suplimentare

- **Auto-fit** — optimizator de tip coordinate-descent care calibrează parametrii de micro-cost pe baza măsurătorilor reale de bancă (minimizare RMSE)
- **Transfer Learning** — estimează costurile pentru proiecte netestate, identificând cel mai apropiat proiect de referință din punct de vedere structural și adaptându-i costurile
- **Depozit colaborativ de date de bancă (Bench Store)** — bază de date SQLite (mod WAL) pentru partajarea costurilor calibrate în echipă; migrează automat din formatul JSON vechi
- **Suită de auto-testare** — validare internă a invarianților (monotonie, determinism, non-negativitate, limite, regresie RMSE)
- **Interfață grafică modernă** — interfață PyQt6 cu temă întunecată, navigator de proiecte, terminal integrat și flux de lucru pe file (tab-uri)
- **CLI independent** — `python -m dem_simulator` pentru utilizare fără interfață grafică / în CI

---

## Capturi de ecran

> Nu sunt incluse capturi de ecran momentan. Pot fi adăugate în `docs/images/` și referențiate aici.

---

## Structura proiectului

```
finalProject/
├── README.md                   # Acest fișier
├── docs/                       # Documentație detaliată (în engleză)
│
└── final1.2/                   # Rădăcina aplicației
    ├── wcs_qt.py               # Punctul de intrare al interfeței grafice
    ├── run_wcs_qt.bat          # Script de lansare pentru Windows
    ├── WoCaSe.spec             # Specificație de build PyInstaller
    │
    ├── wcs_modules/            # Subsistemul A: Instrumentare & Compilare
    │   ├── __init__.py         # Metadate pachet, constante (TD5_PATH etc.)
    │   ├── qt_ui.py            # Interfața grafică PyQt6 (ModernWCSApp, dialoguri, worker)
    │   ├── main.py             # Orchestratorul fluxului de lucru
    │   ├── td5_builder.py      # Integrare cu TD5 CLI (import, compilare)
    │   ├── arxml_processor.py  # Analiză ARXML (extragere NrFmy)
    │   ├── gpt_detector.py     # Detectarea funcțiilor de timp GPT în headere
    │   ├── code_modifier.py    # Instrumentare cod sursă C
    │   ├── xml_modifier.py     # Modificare fișiere CBD/XML
    │   ├── tdcl_modifier.py    # Inserare include-uri TDCL
    │   ├── file_generator.py   # Generare fișiere de configurare (DCNFXML, GRL, CBD)
    │   ├── templates.py        # Șabloane de conținut pentru fișiere
    │   ├── path_utils.py       # Rezolvarea căilor de proiect
    │   ├── logging_config.py   # Configurare logging (dual handler)
    │   ├── simulator_bridge.py # Punte între wcs_modules și dem_simulator
    │   └── assets/             # Iconițe (lego.ico, săgeți, meniu etc.)
    │
    ├── dem_simulator/          # Subsistemul B: Motorul analitic de simulare
    │   ├── __init__.py         # Re-exporturi API public
    │   ├── __main__.py         # Punct de intrare CLI
    │   ├── constants.py        # Praguri, valori implicite MC, parametri de fitting
    │   ├── config.py           # Dataclass-uri ProjectConfig, FrfBlockConfig
    │   ├── costs.py            # Modelul MicroCosts + seturi de costuri calibrate
    │   ├── scenarios.py        # 3 scenarii WCS cu pași de calibrare
    │   ├── engine.py           # DemMainFunctionSimulator (motorul de bază)
    │   ├── extractor.py        # Parser cod sursă C (fără valori hardcodate)
    │   ├── simulation.py       # Grid WCS, RMSE, auto-fit
    │   ├── analysis.py         # Monte Carlo, sensibilitate, comparație variante
    │   ├── transfer_fit.py     # Transfer learning între proiecte
    │   ├── bench_store.py      # API depozit colaborativ
    │   ├── bench_store_db.py   # Strat SQLite (WAL, tranzacții)
    │   ├── excel_report.py     # Generare raport Excel (openpyxl)
    │   ├── selftest.py         # Validare internă a invarianților
    │   ├── exceptions.py       # Ierarhie de excepții custom
    │   └── logging_setup.py    # Logging specific simulatorului
    │
    └── tests/                  # Teste unitare
        ├── wcs_modules/        # Teste pentru wcs_modules (10 fișiere)
        └── dem_simulator/      # Teste pentru dem_simulator (9 fișiere)
```

---

## Cerințe

### Sistem

- **SO:** Windows 10 / 11 (x64)
- **Python:** 3.11+
- **TD5 CLI:** necesar pentru fluxul de Instrumentare+Compilare (nu este necesar pentru modul doar-simulare)

### Pachete Python

| Pachet | Scop | Necesar |
|--------|------|---------|
| `PyQt6` | Interfața grafică | Da (pentru modul GUI) |
| `openpyxl` | Generarea rapoartelor Excel | Opțional (rapoartele sunt dezactivate dacă lipsește) |

---

## Pașii de instalare și lansare a aplicației

### 1. Obținerea proiectului

Dezarhivați/copiați folderul proiectului (`finalProject/`) în locația dorită. Nu este necesar accesul la depozitul Git intern al Schaeffler pentru a rula aplicația local — tot codul necesar este inclus în acest folder.

### 2. Crearea mediului virtual Python

```powershell
cd finalProject
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalarea dependențelor

```powershell
pip install PyQt6 openpyxl
```

### 4. Lansarea aplicației

**Interfața grafică (GUI):**

```powershell
cd final1.2
python wcs_qt.py
# sau folosind scriptul de lansare:
.\run_wcs_qt.bat
```

**Mod linie de comandă (doar simulatorul, fără interfață grafică):**

```powershell
cd final1.2
python -m dem_simulator              # selecție interactivă de proiect
python -m dem_simulator PROJ2        # un singur proiect
python -m dem_simulator ALL          # toate proiectele descoperite
python -m dem_simulator --fit        # calibrează costurile (auto-fit), apoi simulează
python -m dem_simulator --selftest   # rulează validarea internă a invarianților
```

---

## Pașii de compilare ai aplicației (build executabil standalone)

Aplicația poate fi împachetată într-un singur executabil Windows (`.exe`), independent de o instalare Python, folosind **PyInstaller** și specificația de build [`WoCaSe.spec`](final1.2/WoCaSe.spec).

```powershell
# 1. Activați mediul virtual (dacă nu e deja activ)
.venv\Scripts\Activate.ps1

# 2. Instalați PyInstaller
pip install pyinstaller

# 3. Rulați build-ul din folderul aplicației
cd final1.2
pyinstaller WoCaSe.spec

# 4. Executabilul rezultat se află în:
#    final1.2\dist\WoCaSe.exe
```

Fișierul `WoCaSe.spec` include automat toate modulele interne (`wcs_modules`, `dem_simulator`) și resursele grafice din `wcs_modules/assets/`, deci nu sunt necesare configurări suplimentare — calea de proiect este determinată automat pe baza locației fișierului `.spec`.

---

## Configurare

Constantele principale sunt definite în `final1.2/wcs_modules/__init__.py`:

```python
TD5_PATH   = r"C:\LegacyApp\TD5\4.4.0\eclipse_cli\td5.exe"
BUILD_TYPE = "NORMAL"
BUILD_RULE = "All"
```

`TD5_PATH` trebuie ajustat pentru a indica locația reală a executabilului `td5.exe` din mediul de lucru local, dacă se dorește utilizarea fluxului de Instrumentare+Compilare.

Locația depozitului de date de bancă (bench store, `bench_store.db`) poate fi suprascrisă prin variabila de mediu `DEM_BENCH_STORE` sau programatic, prin `bench_store.set_store_path()`. Aceste fișiere sunt create automat la prima rulare și nu sunt incluse în proiectul livrat.

Detalii complete: [docs/configuration.md](docs/configuration.md).

---

## Documentație

Documentația detaliată (în limba engleză) este disponibilă în folderul [`docs/`](docs/):

| Document | Descriere |
|----------|-----------|
| [Architecture](docs/architecture.md) | Arhitectura sistemului, relațiile dintre module, fluxul de date |
| [User Guide](docs/user-guide.md) | Ghid complet de utilizare GUI și CLI |
| [Simulation Model](docs/simulation-model.md) | Modelul matematic, scenariile și parametrii de cost |
| [API Reference](docs/api-reference.md) | API-ul programatic al ambelor subsisteme |
| [Configuration](docs/configuration.md) | Toți parametrii și căile configurabile |
| [Testing](docs/testing.md) | Strategia de testare, rularea testelor, auto-teste |
| [Troubleshooting](docs/troubleshooting.md) | Erori frecvente și soluții |

---

## Testare

```powershell
# Rulează toate testele unitare
cd final1.2
python -m pytest tests/ -v

# Rulează auto-testele simulatorului (validarea invarianților)
python -m dem_simulator --selftest
```

---

## Tehnologii utilizate

| Nivel | Tehnologie |
|-------|-----------|
| Limbaj | Python 3.11 |
| Interfață grafică | PyQt6 (temă întunecată, CSS personalizat) |
| Raportare | openpyxl (grafice, formatare condiționată) |
| Stocare date | SQLite3 (mod WAL, migrare automată din JSON) |
| Analiză/parsare | `re` (regex), `xml.etree.ElementTree` |
| Integrare externă | TD5 CLI (`subprocess`) |
| Împachetare | PyInstaller |
| Testare | unittest / pytest |

---

## Context și confidențialitate

Acest proiect a fost dezvoltat ca instrument intern pentru **Schaeffler** și a fost adaptat pentru a fi prezentat ca proiect de licență. Denumirile reale ale proiectelor auto client (folosite intern pentru calibrarea modelului) au fost înlocuite în cod, teste și documentație cu identificatori generici (`PROJ1`–`PROJ6`); valorile numerice de timp (costurile calibrate) au fost păstrate neschimbate, fiind date ilustrative ale modelului, nu informații confidențiale despre proiecte reale.

## Autor

**Al-Yafeai Yosif**

---

## Licență

> Proiect intern realizat pentru Schaeffler, adaptat pentru lucrarea de licență. Se recomandă adăugarea unui fișier `LICENSE` corespunzător politicii instituției/companiei înainte de o eventuală distribuire publică.
