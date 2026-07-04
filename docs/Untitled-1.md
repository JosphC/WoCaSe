# WoCaSe — Estimator de Timp de Execuție Worst-Case

WoCaSe este un instrument automatizat dezvoltat pentru estimarea timpului de execuție în cel mai defavorabil caz (_Worst-Case Execution Time_ - WCET) al funcției `Icsp_Dem_MainFunction()`, în cadrul proiectelor AUTOSAR.

## Repository Proiect

Codul sursă complet al aplicației este disponibil la următoarea adresă:
[https://github.com/JosphC/WoCaSe](https://github.com/JosphC/WoCaSe)

---

## 1. Descrierea Livrabilelor

Proiectul conține:

- **`wcs_modules/`**: Subsistemul responsabil cu instrumentarea fișierelor C/XML și orchestrarea fluxului de compilare prin TD5 CLI.
- **`dem_simulator/`**: Motorul analitic de simulare, bazat pe un model de micro-costuri, utilizat pentru estimarea WCET și analiza de sensibilitate.
- **`tests/`**: Suită completă de teste unitare pentru validarea funcționalităților modulelor și a invarianților simulatorului.
- **`docs/`**: Documentație tehnică detaliată (arhitectură, ghid utilizator, model matematic).
- **`WoCaSe.spec`**: Specificația pentru generarea executabilului standalone.

---

## 2. Pașii de instalare și lansare a aplicației

### Cerințe de sistem

- Windows 10 / 11 (x64)
- Python 3.11+
- TD5 CLI (necesar pentru fluxul de Instrumentare+Compilare)

### Obținerea proiectului

Dezarhivați/copiați folderul proiectului (`finalProject/`) în locația dorită.

### Crearea mediului virtual Python

```powershell
cd finalProject
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Instalarea dependențelor

```powershell
pip install PyQt6 openpyxl
```

### Lansarea aplicației

**Interfața grafică (GUI):**

```powershell
cd final1.2
python wcs_qt.py
# sau folosind scriptul de lansare:
.\run_wcs_qt.bat
```

---

## 3. Pașii de compilare ai aplicației (build executabil standalone)

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
