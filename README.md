# 🏀 Zastal Calendar

**Mecze Zastalu Zielona Góra w jednym, automatycznie aktualizowanym kalendarzu.**

Zastal Calendar łączy terminarze **ORLEN Basket Ligi** i **FIBA Europe Cup**
w jeden plik iCalendar. Kalendarz można subskrybować w Apple Calendar na iPhonie
i Macu oraz w innych aplikacjach obsługujących subskrypcje `.ics`.

Zmiana terminu, godziny, hali lub przeciwnika aktualizuje istniejące wydarzenie.
Stały adres kalendarza pozwala otrzymywać kolejne aktualizacje bez ponownego
importowania pliku.

## Co oferuje projekt

- **Dwa terminarze w jednym miejscu** — mecze ligowe i europejskie puchary.
- **Oficjalne źródła** — dane pobierane bezpośrednio z serwisów PLK i FIBA.
- **Automatyczne aktualizacje** — workflow GitHub Actions zaplanowany co 6 godzin.
- **Stała tożsamość meczu** — zmiana danych nie tworzy nowego UID wydarzenia.
- **Obsługa TBD** — spotkanie bez ustalonej godziny jest wydarzeniem całodniowym.
- **Poprawne strefy czasowe** — uwzględnienie czasu miejscowego i zmian czasu letniego.
- **Ochrona kalendarza podczas awarii** — błędne lub niepełne dane nie zastępują ostatniego poprawnego pliku.

## Jak wygląda wydarzenie

Przykładowe tytuły:

> 🏀 Zastal – Legia Warszawa  
> 🏀 FIATC Girona – Zastal

Opis zawiera rozgrywki, sezon, gospodarzy i gości, status oraz odnośnik do
oficjalnego źródła. Hala jest dodawana, gdy organizator udostępnia jej dane.
Dla spotkania z ustaloną godziną przyjmowany jest czas trwania **2 godziny 15 minut**.

Jeśli godzina pozostaje nieznana, wydarzenie obejmuje wskazany dzień i otrzymuje
oznaczenie TBD w opisie. Po ogłoszeniu godziny ten sam wpis zmienia się
w wydarzenie godzinowe.

## Jak to działa

Przy każdym uruchomieniu generator pobiera oba terminarze, identyfikuje mecze
Zastalu i normalizuje dane. Następnie porównuje je z poprzednią wersją kalendarza,
sprawdza poprawność wyniku i zapisuje [`docs/zastal.ics`](docs/zastal.ics).

GitHub Actions wykonuje testy, uruchamia generator i publikuje plik przez
GitHub Pages. Commit powstaje tylko wtedy, gdy zawartość kalendarza się zmieniła.
Projekt działa bez własnego serwera i bazy danych.

## Źródła danych

| Rozgrywki | Źródło | Sposób pobierania |
|---|---|---|
| ORLEN Basket Liga | [Oficjalny serwis PLK](https://plk.pl/terminarz) | Dane JSON osadzone w HTML terminarza i szczegółów meczów |
| FIBA Europe Cup | [Oficjalny serwis FIBA](https://www.fiba.basketball/en/events) | Endpoint JSON używany przez witrynę; awaryjnie dane osadzone w oficjalnym HTML |

Sezon jest ustalany na podstawie danych organizatorów. Drużyna jest rozpoznawana
przede wszystkim po identyfikatorach źródłowych, dzięki czemu zmiana nazwy
sponsorskiej nie wyklucza jej spotkań z kalendarza.

## Spójność aktualizacji

UID wydarzenia bazuje na identyfikatorze meczu ze źródła. Zmienione wydarzenie
zachowuje UID, a jego `SEQUENCE` i `LAST-MODIFIED` są aktualizowane. Ponowne
uruchomienie z identycznymi danymi pozostawia plik bez zmian.

Generator wymaga poprawnych danych z obu rozgrywek. Pusta odpowiedź, zniknięcie
znanego meczu, duplikaty lub błąd walidacji przerywają publikację. Nowa wersja
jest zapisywana atomowo dopiero po przejściu kontroli.

## Technologia i testy

Projekt wykorzystuje **Python 3.12+**, `requests`, `BeautifulSoup` i `icalendar`.
Pobieranie odbywa się zwykłym HTTP, bez automatyzacji przeglądarki.

Testy korzystają z lokalnych fixtures i nie wymagają dostępu do internetu.
Obejmują parsowanie źródeł, rozpoznawanie drużyny, daty i strefy czasowe,
TBD, stabilność UID, escapowanie znaków oraz zachowanie podczas awarii.

Weryfikacja z **3 września 2026** zakończyła się wynikiem **79 zaliczonych testów**
i wygenerowaniem **40 wydarzeń: 30 PLK oraz 10 FIBA Europe Cup**.
Szczegóły zawiera [raport weryfikacji](reports/VERIFICATION.md).

## Dokumentacja

- [Wdrożenie, subskrypcja i konfiguracja](SETUP.md)
- [Raport weryfikacji projektu](reports/VERIFICATION.md)
- [Dane i wyniki smoke testu](reports/smoke.json)
- [Workflow aktualizacji i publikacji](.github/workflows/update-calendar.yml)
- [Testy i fixtures](tests/)

Terminy zależą od informacji publikowanych przez organizatorów. Częstotliwość
pobierania zmian przez aplikację kalendarza może różnić się od harmonogramu
generatora. Projekt nie jest oficjalnym kalendarzem klubu, PLK ani FIBA.
