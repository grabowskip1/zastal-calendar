# Fixtures offline

Małe wycinki rzeczywistych oficjalnych danych pobranych 2026-09-03:

- PLK: `https://plk.pl/terminarz`, mecze 223461, 223469, 223493.
- Szczegóły PLK: `https://plk.pl/mecz/223461/enea-laciate-astoria-bydgoszcz-vs-zastal-zielona-gora`.
- FIBA: `https://www.fiba.basketball/en/events` i edycja `fiba-europe-cup-26-27`.
- Gry FIBA: `https://digital-api.fiba.basketball/hapi/getgdapgamesbycompetitionid?gdapCompetitionId=209129`
  oraz identyczne rekordy osadzone w oficjalnym `/games`.

Wybrano znane godziny, TBD, brak przeciwnika, brak hali/strefy i wyjazdy zagraniczne.
Usunięto niepotrzebne obrazki z wycinków PLK. Opakowanie HTML jest minimalne;
JSON pochodzi ze źródła. Celowo podzielono rekord Flight pomiędzy trzy skrypty.
Nie zapisano klucza klienta FIBA ani pełnej konfiguracji strony.
Testy mutują kopie rekordów do symulowania zmian godzin, sponsorów i awarii.
