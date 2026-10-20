// Bestyrelsens indstillinger – læses af siden, robotten og mellemmanden. Ret direkte i GitHub (blyanten ✏️)
// og tryk "Commit changes". Hold formen: tekst i "anførselstegn" og komma mellem linjerne.
//
// mellemmand: adressen på Google-scriptet, der lader alle i bestyrelsen tilføje, tage og rette opgaver uden
//             GitHub-konto (slutter på /exec). Står der ingenting, kan siden kun vise opgaverne. Se README.md.
// asapDage:   hvor mange dage "ASAP" giver som deadline – regnet fra mødet, når tabellen sættes ind, og fra
//             i dag, når man vælger ASAP på siden.
// medlemmer:  bestyrelsen. Kun de her kan få opgaver og vælges som "hvem" – andre navne i referatets
//             Person-kolonne bliver skrevet forrest i opgaven i stedet. "emner" er det, personen tager sig af:
//             står der ikke en fra bestyrelsen på en opgave, lægger robotten den hos den, der har opgavens
//             emne – og har ingen emnet, ligger den hos Bestyrelsen, så alle kan tage den.
//             "rolle" må stå i Person-kolonnen i stedet for navnet (fx "Kassererne" = Mikkel og Lars).
//             Emnerne er: Økonomi, Sponsorer & fonde, Hold & turneringer, Trænere & kurser, Ungdom,
//             Arrangementer & frivillige, Tøj & udstyr, Kommunikation, Haller & lokaler,
//             Forening & bestyrelse.
window.BESTYRELSE = {
  "mellemmand": "https://script.google.com/macros/s/AKfycbxsUMJSV3cFf1Na7_tfQJyygTDwYpoSdnDfMetk6PAgWUJK0uyW1v-3vgaHSzits_47lA/exec",
  "asapDage": 7,
  "medlemmer": [
    { "navn": "Søren",  "rolle": "formand",          "emner": ["Forening & bestyrelse"] },
    { "navn": "Heidi",  "rolle": "sponsoransvarlig", "emner": ["Sponsorer & fonde"] },
    { "navn": "Anna",   "rolle": "ungdomsansvarlig", "emner": ["Ungdom"] },
    { "navn": "Emma",   "rolle": "materialeansvarlig", "emner": ["Tøj & udstyr"] },
    { "navn": "Ida",    "rolle": "festansvarlig",    "emner": ["Arrangementer & frivillige"] },
    { "navn": "Sonja",  "rolle": "",                 "emner": [] },
    { "navn": "Mikkel", "rolle": "kasserer",         "emner": ["Økonomi"] },
    { "navn": "Lars",   "rolle": "kasserer",         "emner": ["Økonomi"] },
    { "navn": "Marcel", "rolle": "kredsansvarlig",   "emner": ["Hold & turneringer"] }
  ]
};
