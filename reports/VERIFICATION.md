# Raport weryfikacji — 3 września 2026

## Wynik

Projekt uruchomiono z Pythonem **3.12.13**. Zależności zostały faktycznie
zainstalowane. Końcowy zestaw: **79 testów zaliczonych, 0 błędów**.

```text
79 passed in 0.68s
VALID: 40 events, unique UIDs, chronological order, {'fiba': 10, 'plk': 30}
SUCCESS: 40 games, changed=True, timed=8, TBD=32
```

Plik końcowy: `docs/zastal.ics`, **44 484 bajty**.
Ostatnie pełne pobranie: **2026-09-03 16:15:57 UTC**.
Log `generation.log` używa lokalnego zegara środowiska (UTC−4);
daty w raporcie JSON i znaczniki godzinowe ICS mają jawny UTC.

SHA-256:

```text
07025e1c0b5b0fb3514c3cfa23f3184ae0e4f436dac4a43d80abc79ae316c5d0
```

| Sprawdzenie | Wynik |
|---|---|
| PLK, sezon 2026/2027 | 30 meczów, w tym 5 z godziną i 25 TBD |
| FIBA Europe Cup, sezon 2026/2027 | 10 meczów, w tym 3 z godziną i 7 TBD |
| Źródła | Rzeczywiste odpowiedzi HTTP oficjalnych serwisów |
| Zakres dat | 03.10.2026 – 06.05.2027 |
| UID | 40 różnych UID dla 40 wydarzeń |
| Zdublowane spotkania | 0 |
| Kolejność | Chronologiczna; sprawdzona walidatorem |
| Składnia | VCALENDAR/2.0, komplet wymaganych pól, parsowanie biblioteką icalendar |
| Kodowanie | UTF-8, CRLF, linie do 75 oktetów, polskie znaki i escaping |
| Godziny | UTC; zgodność z lokalnym czasem źródła i regułami DST |
| TBD | Data całodniowa i wyłączny DTEND następnego dnia |
| Czas trwania meczów godzinowych | 2 godz. 15 min |
| Drugie pełne pobranie bez zmian | `changed=False`, identyczne bajty i UID |
| Odtworzenie końcowej wersji z raportu | Identyczne bajty, mimo późniejszego czasu uruchomienia |
| Awaria źródła / zniknięcie meczu / błąd dysku | Testy potwierdzają zachowanie starego pliku |
| Workflow | Poprawny YAML, sprawdzone wyzwalacze, zakres uprawnień i zależność deploy |

`smoke.json` zawiera znormalizowane dane wszystkich 40 meczów, wynik kontroli,
sumę kontrolną i timestamp pobrania. `tests.txt` to zapis końcowego uruchomienia pytest.

## Weryfikacja oficjalnych źródeł

**PLK:** [oficjalny terminarz](https://plk.pl/terminarz), strukturalny JSON
w odpowiedzi HTML/Next.js, pełna tablica `schedule` i linkowane strony meczów.
Weryfikacja szczegółów pobrała **30 stron meczów**. W bieżących danych ich hale
nie są jeszcze wpisane (`venue.id=null`); dlatego nie przypisano hali domowej
na podstawie samej nazwy gospodarza. Sezon 29 → 2026/2027 pochodzi z odpowiedzi.

**PZKosz:** [oficjalny terminarz zespołu 769](https://rozgrywki.pzkosz.pl/liga/2/druzyny/d/769/orlen-zastal-zielona-gora/terminarz.html)
potwierdza drużynę, daty i znaczenie pustej godziny. Część godzin była tam
nieuzupełniona w porównaniu z PLK, więc nie przyjęto go jako głównego źródła.

**FIBA:** katalog [wydarzeń](https://www.fiba.basketball/en/events)
wskazał [edycję 2026/2027](https://www.fiba.basketball/en/events/fiba-europe-cup-26-27).
Metadane potwierdziły competition ID **209129**, kod **ECM2**, organizację Zastalu
**10024** i sezonowy team ID **285088**. Endpoint używany przez frontend:

```text
https://digital-api.fiba.basketball/hapi/getgdapgamesbycompetitionid?gdapCompetitionId=209129
```

Żądanie bez nagłówka klienta zwróciło 401, a z publiczną konfiguracją odczytaną
z witryny — 200 i tablicę 308 rekordów całych rozgrywek. Spośród nich wybrano
10 meczów Zastalu. Nie zapisano wartości klucza w projekcie.
[Oficjalna strona `/games`](https://www.fiba.basketball/en/events/fiba-europe-cup-26-27/games)
także udostępnia pełne rekordy jako JSON w HTML; odczytano je i sprawdzono
jako alternatywę dla API. Test awarii API potwierdza użycie tej drogi.

## Ręczna kontrola wybranych spotkań

Daty i godziny poniżej porównano z oficjalnymi terminarzami oraz danymi
na stronach poszczególnych meczów. Dodatkowe pobranie stron FIBA dla Szolnoku,
Girony i Ostendy potwierdziło UTC, lokalny czas, strefę IANA oraz halę niezależnie
od listy meczów API.

| Oficjalny mecz | Data i czas miejscowy / TBD | DTSTART w ICS |
|---|---|---|
| [Astoria – Zastal, PLK 223461](https://plk.pl/mecz/223461/enea-laciate-astoria-bydgoszcz-vs-zastal-zielona-gora) | 03.10.2026 17:30, Europe/Warsaw | 20261003T153000Z |
| [Szolnoki – Zastal, FIBA 135695](https://www.fiba.basketball/en/events/fiba-europe-cup-26-27/games/135695-OLAJ-ZIE) | 06.10.2026 18:00, Europe/Budapest | 20261006T160000Z |
| [Zastal – Legia, PLK 223469](https://plk.pl/mecz/223469/zastal-zielona-gora-vs-legia-warszawa) | 09.10.2026 20:15, Europe/Warsaw | 20261009T181500Z |
| [Girona – Zastal, FIBA 135702](https://www.fiba.basketball/en/events/fiba-europe-cup-26-27/games/135702-GIR-ZIE) | 20.10.2026 20:00, Europe/Madrid | 20261020T180000Z |
| [Toruń – Zastal, PLK 223493](https://plk.pl/mecz/223493/arriva-lotto-twarde-pierniki-torun-vs-zastal-zielona-gora) | 31.10.2026, TBD (`00:00` w PLK) | VALUE=DATE:20261031 |
| [Zastal – Girona, FIBA 135717](https://www.fiba.basketball/en/events/fiba-europe-cup-26-27/games/135717-ZIE-GIR) | 09.12.2026, TBD | VALUE=DATE:20261209 |
| [Oostende – Zastal, FIBA 135719](https://www.fiba.basketball/en/events/fiba-europe-cup-26-27/games/135719-BCO-ZIE) | 15.12.2026 20:30, Europe/Brussels | 20261215T193000Z |

Potwierdzone hale FIBA: Varosi Sportcsarnok (Szolnok), Pavello Fontajau (Girona),
COREtec Dôme (Oostende), Centrum Rekreacyjno-Sportowe Zielona Gora (mecze domowe).
Wyjazdy z nieustalonym przeciwnikiem i halą nie dostały wymyślonej lokalizacji.

## Znalezione problemy i poprawki

1. **403 FIBA przy domyślnym żądaniu:** oficjalne strony stały się dostępne
   zwykłym HTTP z nagłówkami `User-Agent` i `Accept`. Nie użyto przeglądarki.
2. **401 API FIBA:** ustalono wymagany publiczny nagłówek klienta i pobieranie
   jego wartości z bieżącej konfiguracji witryny. Dodano alternatywne dane z HTML.
3. **PLK `00:00` i poprzedni dzień w UTC:** np. mecz 31 października ma
   placeholder UTC 30 października 23:00. Wydarzenie całodniowe bierze datę
   miejscową 31 października. Test regresji sprawdza dokładnie ten przypadek.
4. **FIBA godzina bez `Z`:** pole `gameDateTimeUTC` ma jawne znaczenie UTC,
   mimo braku suffixu. Potwierdzono je względem `gameDateTime` i `ianaTimeZone`.
5. **Nieznany przeciwnik FIBA:** ID meczu istnieje wcześniej niż komplet drużyn.
   Zachowano wydarzenie i UID. Oficjalny numeryczny URL strony zwrócił 200
   z `Content Unavailable`; takie wpisy linkują teraz do terminarza rozgrywek.
6. **Test odczytu tekstu iCalendar:** poprawiono niepotrzebne `.decode()`,
   ponieważ zainstalowana wersja biblioteki zwraca już tekst. Escaping,
   wielobajtowe polskie znaki i składanie linii przechodzą końcowe testy.
7. **Publikacja GitHub Pages:** uwzględniono brak automatycznego buildu Pages
   po pushu `GITHUB_TOKEN`; workflow jawnie publikuje artefakt z `docs`.
8. **Przejściowe timeouty podczas powtórnego pobrania:** retry zakończyło się
   sukcesem bez zmiany kalendarza. Testy oddzielnie sprawdzają trwałą awarię
   i zachowanie poprzedniego pliku.

## Granice wykonanej weryfikacji

Wykonano instalację, testy jednostkowe, trzy pełne pobrania na żywo,
generowanie ICS, porównanie powtórnego wyniku, kontrolę wybranych stron
i walidację workflow jako YAML. Końcowe trzecie pobranie obejmuje poprawkę
linków meczów z nieznanym przeciwnikiem; replay końcowych rekordów jest identyczny.

Nie uruchamiano GitHub Actions na koncie właściciela i nie testowano subskrypcji
na fizycznym iPhonie/Macu. Wdrożenie wymaga utworzenia repozytorium oraz
włączenia Pages zgodnie z README. Plik ma standardową strukturę iCalendar
do subskrypcji, ale nie deklarujemy wykonanego testu urządzenia.

Ryzyka utrzymania: zmiany niepublicznego kontraktu API/Next.js, blokady HTTP,
usunięcie meczu lub zmiana jego ID, niepełna edycja nowego sezonu, wyłączony cron,
ochrona gałęzi i opóźnienia klienta Apple. Projekt wykrywa błędy i zachowuje
ostatni dobry plik; nie obiecuje nieprzerwanej dostępności zewnętrznych serwisów.
