PRD — Lokalni AI Coding Agent
1. Overview

Cilj projekta je napraviti lokalni AI coding agent koji može generisati, analizirati i menjati kod bez korišćenja cloud AI servisa.

Sistem koristi:

Ollama za lokalno pokretanje LLM modela
Qwen2.5-Coder kao glavni coding model
DeepSeek Coder za dodatno reasoning i analizu koda
claw-code kao agent framework - https://github.com/instructkr/claw-code.git (claw-code je popularni open-source GitHub repozitorij koji implementira AI “coding agent” framework inspirisan arhitekturom Claude Code-a. Nastao je kao “clean-room” (pravna i tehnička) ponovna implementacija nakon curenja izvornog koda alata Claude Code početkom 2026, i vrlo brzo je postao jedan od najbrže rastućih repozitorijuma na GitHub-u.)

Rezultat je lokalni AI developer agent koji može:

generisati kod
analizirati repo
pomagati u razvoju aplikacija
raditi bez API troškova
2. Goals

Primarni ciljevi:

Eliminisati potrebu za cloud AI servisima
Omogućiti lokalno generisanje koda
Kreirati AI asistenta za programiranje
Omogućiti eksperimentisanje sa agent sistemima

Sekundarni ciljevi:

razvoj AI development workflow-a
testiranje open-source LLM modela
razvoj sopstvenih AI development alata
3. System Architecture

Sistem se sastoji iz četiri glavne komponente.

LLM Engine

LLM engine pokreće modele lokalno.

Koristi se:

Ollama

Funkcije:

upravljanje modelima
inference engine
model runtime
Coding Model

Glavni model za generisanje koda:

Qwen2.5-Coder

Karakteristike:

treniran specifično za programiranje
veliki kontekst (128k)
odlični rezultati na coding benchmark testovima
Reasoning Model

Sekundarni model:

DeepSeek Coder

Koristi se za:

analizu koda
debugging
planiranje rešavanja problema
Agent Framework

Agent orchestrator:

claw-code

Funkcije:

upravljanje taskovima
interakcija sa LLM modelima
analiza projekata
4. Hardware Requirements
Minimum requirements
16 GB RAM
4 GB VRAM
SSD storage
modern CPU
Recommended requirements
32 GB RAM
8-12 GB VRAM
SSD
modern CPU
5. Target Hardware (Current System)

Ovaj projekat je dizajniran za sledeću konfiguraciju:

CPU
Intel Core Ultra 9 275HX

RAM
32 GB DDR5

GPU
12 GB VRAM

Storage
≈1 TB SSD

Operativni sistem
Windows 10 / Windows 11

6. Performance Expectations

Sa ovom konfiguracijom očekuje se:

Model	Speed	RAM usage
Qwen2.5-Coder 7B	20-40 tokens/s	6-10 GB
DeepSeek Coder 6.7B	20-35 tokens/s	6-9 GB

Sistem može pokretati modele lokalno bez većih problema.

7. Storage Requirements

Modeli zahtevaju određeni prostor.

Model	Storage
Qwen2.5-Coder 7B	~5 GB
DeepSeek Coder 6.7B	~4 GB

Ukupno:

≈ 9-10 GB

Framework i dependencies:

≈ 1-2 GB

Ukupno:

≈ 12 GB

8. System Impact

Kada modeli rade:

RAM usage: 6-10 GB
CPU usage: 30-60%
GPU VRAM: 5-7 GB

Kada modeli nisu pokrenuti:

CPU usage: ~0%
VRAM: 0
RAM: minimalan

Sistem ne utiče na performanse računara kada nije aktivan.

9. Installation Plan
Step 1 — Install Ollama

Instalirati:

Ollama

Download:

https://ollama.com

Nakon instalacije proveriti:

ollama --version
Step 2 — Install Coding Model

Pokrenuti:

ollama run qwen2.5-coder:7b

Model će se automatski preuzeti (~5 GB).

Step 3 — Install Reasoning Model

Pokrenuti:

ollama pull deepseek-coder:6.7b

Download ≈ 4 GB.

Step 4 — Install Git

Instalirati:

Git

Test:

git --version
Step 5 — Install Python

Instalirati:

Python

Preporučena verzija:

Python 3.11+

Test:

python --version
Step 6 — Clone Repository

Klonirati:

git clone https://github.com/instructkr/claw-code

Zatim:

cd claw-code
Step 7 — Install Dependencies

Instalirati Python pakete:

pip install requests rich typer
Step 8 — Test Framework

Pokrenuti:

python -m src.main summary

Ako sistem vrati output — instalacija je uspešna.

10. Future Improvements

Potencijalna unapređenja sistema:

UI interfejs za AI coding
automatsko refaktorisanje projekata
integracija sa GitHub
multi-agent coding workflow
lokalni IDE plugin
11. Risks

Glavni rizici:

open source modeli su slabiji od komercijalnih
lokalni inference može biti sporiji
agent framework je još u razvoju
12. Expected Outcome

Nakon instalacije sistem omogućava:

lokalni AI coding assistant
generisanje koda bez API troškova
eksperimentisanje sa AI agentima

Sistem funkcioniše kao lokalna alternativa cloud AI coding alatima.
---------------
detaljna specifikacija racunara ovog na kome pravimo ovo 

OS Name	Microsoft Windows 11 Pro
Version	10.0.26200 Build 26200
Other OS Description 	Not Available
OS Manufacturer	Microsoft Corporation
System Name	DESKTOP-0JSV1TR
System Manufacturer	LENOVO
System Model	83LU
System Type	x64-based PC
System SKU	LENOVO_MT_83LU_BU_idea_FM_Legion Pro 5 16IAX10H
Processor	Intel(R) Core(TM) Ultra 9 275HX, 2700 Mhz, 24 Core(s), 24 Logical Processor(s)
BIOS Version/Date	LENOVO Q6CN26WW, 1.5.2025.
SMBIOS Version	3.6
Embedded Controller Version	1.26
BIOS Mode	UEFI
BaseBoard Manufacturer	LENOVO
BaseBoard Product	LNVNB161216
BaseBoard Version	NO DPK
Platform Role	Mobile
Secure Boot State	Off
PCR7 Configuration	Elevation Required to View
Windows Directory	C:\WINDOWS
System Directory	C:\WINDOWS\system32
Boot Device	\Device\HarddiskVolume1
Locale	United Kingdom
Hardware Abstraction Layer	Version = "10.0.26100.1"
Username	DESKTOP-0JSV1TR\Tea
Time Zone	Central Europe Summer Time
Installed Physical Memory (RAM)	32,0 GB
Total Physical Memory	31,4 GB
Available Physical Memory	15,1 GB
Total Virtual Memory	33,4 GB
Available Virtual Memory	10,3 GB
Page File Space	2,00 GB
Page File	C:\pagefile.sys
Kernel DMA Protection	On
Virtualisation-based security	Running
Virtualisation-based security required security properties	Base Virtualisation Support
Virtualisation-based security available security properties	Base Virtualisation Support, DMA Protection, UEFI Code Readonly, SMM Security Mitigations 1.0, Mode Based Execution Control, APIC Virtualisation
Virtualisation-based security services configured	Hypervisor enforced Code Integrity
Virtualisation-based security services running	Hypervisor enforced Code Integrity
App Control for Business policy	Enforced
App Control for Business user mode policy	Off
Automatic Device Encryption Support	Elevation Required to View
A hypervisor has been detected. Features required for Hyper-V will not be displayed.	
