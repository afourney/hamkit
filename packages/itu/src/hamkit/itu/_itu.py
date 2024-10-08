# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT
from typing import NamedTuple, List


class ItuPrefix(NamedTuple):
    prefix: str
    country_name: str
    country_code: str


# Based on https://en.wikipedia.org/wiki/ITU_prefix#Allocation_table
ITU_PREFIXES = [
    ItuPrefix("HB3Y", "Liechtenstein", "LI"),
    ItuPrefix("HB0", "Liechtenstein", "LI"),
    ItuPrefix("HBL", "Liechtenstein", "LI"),
    ItuPrefix("SSA", "Egypt", "EG"),
    ItuPrefix("SSB", "Egypt", "EG"),
    ItuPrefix("SSC", "Egypt", "EG"),
    ItuPrefix("SSD", "Egypt", "EG"),
    ItuPrefix("SSE", "Egypt", "EG"),
    ItuPrefix("SSF", "Egypt", "EG"),
    ItuPrefix("SSG", "Egypt", "EG"),
    ItuPrefix("SSH", "Egypt", "EG"),
    ItuPrefix("SSI", "Egypt", "EG"),
    ItuPrefix("SSJ", "Egypt", "EG"),
    ItuPrefix("SSK", "Egypt", "EG"),
    ItuPrefix("SSL", "Egypt", "EG"),
    ItuPrefix("SSM", "Egypt", "EG"),
    ItuPrefix("SSN", "Sudan", "SD"),
    ItuPrefix("SSO", "Sudan", "SD"),
    ItuPrefix("SSP", "Sudan", "SD"),
    ItuPrefix("SSQ", "Sudan", "SD"),
    ItuPrefix("SSR", "Sudan", "SD"),
    ItuPrefix("SSS", "Sudan", "SD"),
    ItuPrefix("SST", "Sudan", "SD"),
    ItuPrefix("SSU", "Sudan", "SD"),
    ItuPrefix("SSV", "Sudan", "SD"),
    ItuPrefix("SSW", "Sudan", "SD"),
    ItuPrefix("SSX", "Sudan", "SD"),
    ItuPrefix("SSY", "Sudan", "SD"),
    ItuPrefix("SSZ", "Sudan", "SD"),
    ItuPrefix("3DA", "Eswatini", "SZ"),
    ItuPrefix("3DB", "Eswatini", "SZ"),
    ItuPrefix("3DC", "Eswatini", "SZ"),
    ItuPrefix("3DD", "Eswatini", "SZ"),
    ItuPrefix("3DE", "Eswatini", "SZ"),
    ItuPrefix("3DF", "Eswatini", "SZ"),
    ItuPrefix("3DG", "Eswatini", "SZ"),
    ItuPrefix("3DH", "Eswatini", "SZ"),
    ItuPrefix("3DI", "Eswatini", "SZ"),
    ItuPrefix("3DJ", "Eswatini", "SZ"),
    ItuPrefix("3DK", "Eswatini", "SZ"),
    ItuPrefix("3DL", "Eswatini", "SZ"),
    ItuPrefix("3DM", "Eswatini", "SZ"),
    ItuPrefix("3DN", "Fiji", "FJ"),
    ItuPrefix("3DO", "Fiji", "FJ"),
    ItuPrefix("3DP", "Fiji", "FJ"),
    ItuPrefix("3DQ", "Fiji", "FJ"),
    ItuPrefix("3DR", "Fiji", "FJ"),
    ItuPrefix("3DS", "Fiji", "FJ"),
    ItuPrefix("3DT", "Fiji", "FJ"),
    ItuPrefix("3DU", "Fiji", "FJ"),
    ItuPrefix("3DV", "Fiji", "FJ"),
    ItuPrefix("3DW", "Fiji", "FJ"),
    ItuPrefix("3DX", "Fiji", "FJ"),
    ItuPrefix("3DY", "Fiji", "FJ"),
    ItuPrefix("3DZ", "Fiji", "FJ"),
    ItuPrefix("AA", "United States", "US"),
    ItuPrefix("AB", "United States", "US"),
    ItuPrefix("AC", "United States", "US"),
    ItuPrefix("AD", "United States", "US"),
    ItuPrefix("AE", "United States", "US"),
    ItuPrefix("AF", "United States", "US"),
    ItuPrefix("AG", "United States", "US"),
    ItuPrefix("AH", "United States", "US"),
    ItuPrefix("AI", "United States", "US"),
    ItuPrefix("AJ", "United States", "US"),
    ItuPrefix("AK", "United States", "US"),
    ItuPrefix("AL", "United States", "US"),
    ItuPrefix("AM", "Spain", "ES"),
    ItuPrefix("AN", "Spain", "ES"),
    ItuPrefix("AO", "Spain", "ES"),
    ItuPrefix("AP", "Pakistan", "PK"),
    ItuPrefix("AQ", "Pakistan", "PK"),
    ItuPrefix("AR", "Pakistan", "PK"),
    ItuPrefix("AS", "Pakistan", "PK"),
    ItuPrefix("AT", "India", "IN"),
    ItuPrefix("AU", "India", "IN"),
    ItuPrefix("AV", "India", "IN"),
    ItuPrefix("AW", "India", "IN"),
    ItuPrefix("AX", "Australia", "AU"),
    ItuPrefix("AY", "Argentina", "AR"),
    ItuPrefix("AZ", "Argentina", "AR"),
    ItuPrefix("A2", "Botswana", "BW"),
    ItuPrefix("A3", "Tonga", "TO"),
    ItuPrefix("A4", "Oman", "OM"),
    ItuPrefix("A5", "Bhutan", "BT"),
    ItuPrefix("A6", "United Arab Emirates", "AE"),
    ItuPrefix("A7", "Qatar", "QA"),
    ItuPrefix("A8", "Liberia", "LR"),
    ItuPrefix("A9", "Bahrain", "BH"),
    ItuPrefix("BM", "Taiwan", "TW"),
    ItuPrefix("BN", "Taiwan", "TW"),
    ItuPrefix("BO", "Taiwan", "TW"),
    ItuPrefix("BP", "Taiwan", "TW"),
    ItuPrefix("BQ", "Taiwan", "TW"),
    ItuPrefix("BU", "Taiwan", "TW"),
    ItuPrefix("BV", "Taiwan", "TW"),
    ItuPrefix("BW", "Taiwan", "TW"),
    ItuPrefix("BX", "Taiwan", "TW"),
    ItuPrefix("CA", "Chile", "CL"),
    ItuPrefix("CB", "Chile", "CL"),
    ItuPrefix("CC", "Chile", "CL"),
    ItuPrefix("CD", "Chile", "CL"),
    ItuPrefix("CE", "Chile", "CL"),
    ItuPrefix("CF", "Canada", "CA"),
    ItuPrefix("CG", "Canada", "CA"),
    ItuPrefix("CH", "Canada", "CA"),
    ItuPrefix("CI", "Canada", "CA"),
    ItuPrefix("CJ", "Canada", "CA"),
    ItuPrefix("CK", "Canada", "CA"),
    ItuPrefix("CL", "Cuba", "CU"),
    ItuPrefix("CM", "Cuba", "CU"),
    ItuPrefix("CN", "Morocco", "MA"),
    ItuPrefix("CO", "Cuba", "CU"),
    ItuPrefix("CP", "Bolivia", "BO"),
    ItuPrefix("CQ", "Portugal", "PT"),
    ItuPrefix("CR", "Portugal", "PT"),
    ItuPrefix("CS", "Portugal", "PT"),
    ItuPrefix("CT", "Portugal", "PT"),
    ItuPrefix("CU", "Portugal", "PT"),
    ItuPrefix("CV", "Uruguay", "UY"),
    ItuPrefix("CW", "Uruguay", "UY"),
    ItuPrefix("CX", "Uruguay", "UY"),
    ItuPrefix("CY", "Canada", "CA"),
    ItuPrefix("CZ", "Canada", "CA"),
    ItuPrefix("C2", "Nauru", "NR"),
    ItuPrefix("C3", "Andorra", "AD"),
    ItuPrefix("C4", "Cyprus", "CY"),
    ItuPrefix("C5", "The Gambia", "GM"),
    ItuPrefix("C6", "Bahamas", "BS"),
    ItuPrefix("C7", "World Meteorological Organization", None),
    ItuPrefix("C8", "Mozambique", "MZ"),
    ItuPrefix("C9", "Mozambique", "MZ"),
    ItuPrefix("DA", "Germany", "DE"),
    ItuPrefix("DB", "Germany", "DE"),
    ItuPrefix("DC", "Germany", "DE"),
    ItuPrefix("DD", "Germany", "DE"),
    ItuPrefix("DE", "Germany", "DE"),
    ItuPrefix("DF", "Germany", "DE"),
    ItuPrefix("DG", "Germany", "DE"),
    ItuPrefix("DH", "Germany", "DE"),
    ItuPrefix("DI", "Germany", "DE"),
    ItuPrefix("DJ", "Germany", "DE"),
    ItuPrefix("DK", "Germany", "DE"),
    ItuPrefix("DL", "Germany", "DE"),
    ItuPrefix("DM", "Germany", "DE"),
    ItuPrefix("DN", "Germany", "DE"),
    ItuPrefix("DO", "Germany", "DE"),
    ItuPrefix("DP", "Germany", "DE"),
    ItuPrefix("DQ", "Germany", "DE"),
    ItuPrefix("DR", "Germany", "DE"),
    ItuPrefix("DS", "South Korea", "KR"),
    ItuPrefix("DT", "South Korea", "KR"),
    ItuPrefix("DU", "Philippines", "PH"),
    ItuPrefix("DV", "Philippines", "PH"),
    ItuPrefix("DW", "Philippines", "PH"),
    ItuPrefix("DX", "Philippines", "PH"),
    ItuPrefix("DY", "Philippines", "PH"),
    ItuPrefix("DZ", "Philippines", "PH"),
    ItuPrefix("D2", "Angola", "AO"),
    ItuPrefix("D3", "Angola", "AO"),
    ItuPrefix("D4", "Cape Verde", "CV"),
    ItuPrefix("D5", "Liberia", "LR"),
    ItuPrefix("D6", "Comoros", "KM"),
    ItuPrefix("D7", "South Korea", "KR"),
    ItuPrefix("D8", "South Korea", "KR"),
    ItuPrefix("D9", "South Korea", "KR"),
    ItuPrefix("EA", "Spain", "ES"),
    ItuPrefix("EB", "Spain", "ES"),
    ItuPrefix("EC", "Spain", "ES"),
    ItuPrefix("ED", "Spain", "ES"),
    ItuPrefix("EE", "Spain", "ES"),
    ItuPrefix("EF", "Spain", "ES"),
    ItuPrefix("EG", "Spain", "ES"),
    ItuPrefix("EH", "Spain", "ES"),
    ItuPrefix("EI", "Ireland", "IE"),
    ItuPrefix("EJ", "Ireland", "IE"),
    ItuPrefix("EK", "Armenia", "AM"),
    ItuPrefix("EL", "Liberia", "LR"),
    ItuPrefix("EM", "Ukraine", "UA"),
    ItuPrefix("EN", "Ukraine", "UA"),
    ItuPrefix("EO", "Ukraine", "UA"),
    ItuPrefix("EP", "Iran", "IR"),
    ItuPrefix("EQ", "Iran", "IR"),
    ItuPrefix("ER", "Moldova", "MD"),
    ItuPrefix("ES", "Estonia", "EE"),
    ItuPrefix("ET", "Ethiopia", "ET"),
    ItuPrefix("EU", "Belarus", "BY"),
    ItuPrefix("EV", "Belarus", "BY"),
    ItuPrefix("EW", "Belarus", "BY"),
    ItuPrefix("EX", "Kyrgyzstan", "KG"),
    ItuPrefix("EY", "Tajikistan", "TJ"),
    ItuPrefix("EZ", "Turkmenistan", "TM"),
    ItuPrefix("E2", "Thailand", "TH"),
    ItuPrefix("E3", "Eritrea", "ER"),
    ItuPrefix("E4", "Palestinian Authority", "PS"),
    ItuPrefix("E5", "Cook Islands", "CK"),
    ItuPrefix("E7", "Bosnia-Herzegovina", "BA"),
    ItuPrefix("HA", "Hungary", "HU"),
    ItuPrefix("HB", "Switzerland", "CH"),
    ItuPrefix("HC", "Ecuador", "EC"),
    ItuPrefix("HD", "Ecuador", "EC"),
    ItuPrefix("HE", "Switzerland", "CH"),
    ItuPrefix("HF", "Poland", "PL"),
    ItuPrefix("HG", "Hungary", "HU"),
    ItuPrefix("HH", "Haiti", "HT"),
    ItuPrefix("HI", "Dominican Republic", "DO"),
    ItuPrefix("HJ", "Colombia", "CO"),
    ItuPrefix("HK", "Colombia", "CO"),
    ItuPrefix("HL", "South Korea", "KR"),
    ItuPrefix("HM", "North Korea", "KP"),
    ItuPrefix("HN", "Iraq", "IQ"),
    ItuPrefix("HO", "Panama", "PA"),
    ItuPrefix("HP", "Panama", "PA"),
    ItuPrefix("HQ", "Honduras", "HN"),
    ItuPrefix("HR", "Honduras", "HN"),
    ItuPrefix("HS", "Thailand", "TH"),
    ItuPrefix("HT", "Nicaragua", "NI"),
    ItuPrefix("HU", "El Salvador", "SV"),
    ItuPrefix("HV", "Vatican City", "VA"),
    ItuPrefix("HW", "France", "FR"),
    ItuPrefix("HX", "France", "FR"),
    ItuPrefix("HY", "France", "FR"),
    ItuPrefix("HZ", "Saudi Arabia", "SA"),
    ItuPrefix("H2", "Cyprus", "CY"),
    ItuPrefix("H3", "Panama", "PA"),
    ItuPrefix("H4", "Solomon Islands", "SB"),
    ItuPrefix("H6", "Nicaragua", "NI"),
    ItuPrefix("H7", "Nicaragua", "NI"),
    ItuPrefix("H8", "Panama", "PA"),
    ItuPrefix("H9", "Panama", "PA"),
    ItuPrefix("JA", "Japan", "JP"),
    ItuPrefix("JB", "Japan", "JP"),
    ItuPrefix("JC", "Japan", "JP"),
    ItuPrefix("JD", "Japan", "JP"),
    ItuPrefix("JE", "Japan", "JP"),
    ItuPrefix("JF", "Japan", "JP"),
    ItuPrefix("JG", "Japan", "JP"),
    ItuPrefix("JH", "Japan", "JP"),
    ItuPrefix("JI", "Japan", "JP"),
    ItuPrefix("JJ", "Japan", "JP"),
    ItuPrefix("JK", "Japan", "JP"),
    ItuPrefix("JL", "Japan", "JP"),
    ItuPrefix("JM", "Japan", "JP"),
    ItuPrefix("JN", "Japan", "JP"),
    ItuPrefix("JO", "Japan", "JP"),
    ItuPrefix("JP", "Japan", "JP"),
    ItuPrefix("JQ", "Japan", "JP"),
    ItuPrefix("JR", "Japan", "JP"),
    ItuPrefix("JS", "Japan", "JP"),
    ItuPrefix("JT", "Mongolia", "MN"),
    ItuPrefix("JU", "Mongolia", "MN"),
    ItuPrefix("JV", "Mongolia", "MN"),
    ItuPrefix("JW", "Norway", "NO"),
    ItuPrefix("JX", "Norway", "NO"),
    ItuPrefix("JY", "Jordan", "JO"),
    ItuPrefix("JZ", "Indonesia", "ID"),
    ItuPrefix("J2", "Djibouti", "DJ"),
    ItuPrefix("J3", "Grenada", "GD"),
    ItuPrefix("J4", "Greece", "GR"),
    ItuPrefix("J5", "Guinea-Bissau", "GW"),
    ItuPrefix("J6", "Saint Lucia", "LC"),
    ItuPrefix("J7", "Dominica", "DM"),
    ItuPrefix("J8", "Saint Vincent and the Grenadines", "VC"),
    ItuPrefix("LA", "Norway", "NO"),
    ItuPrefix("LB", "Norway", "NO"),
    ItuPrefix("LC", "Norway", "NO"),
    ItuPrefix("LD", "Norway", "NO"),
    ItuPrefix("LE", "Norway", "NO"),
    ItuPrefix("LF", "Norway", "NO"),
    ItuPrefix("LG", "Norway", "NO"),
    ItuPrefix("LH", "Norway", "NO"),
    ItuPrefix("LI", "Norway", "NO"),
    ItuPrefix("LJ", "Norway", "NO"),
    ItuPrefix("LK", "Norway", "NO"),
    ItuPrefix("LL", "Norway", "NO"),
    ItuPrefix("LM", "Norway", "NO"),
    ItuPrefix("LN", "Norway", "NO"),
    ItuPrefix("LO", "Argentina", "AR"),
    ItuPrefix("LP", "Argentina", "AR"),
    ItuPrefix("LQ", "Argentina", "AR"),
    ItuPrefix("LR", "Argentina", "AR"),
    ItuPrefix("LS", "Argentina", "AR"),
    ItuPrefix("LT", "Argentina", "AR"),
    ItuPrefix("LU", "Argentina", "AR"),
    ItuPrefix("LV", "Argentina", "AR"),
    ItuPrefix("LW", "Argentina", "AR"),
    ItuPrefix("LX", "Luxembourg", "LU"),
    ItuPrefix("LY", "Lithuania", "LT"),
    ItuPrefix("LZ", "Bulgaria", "BG"),
    ItuPrefix("L2", "Argentina", "AR"),
    ItuPrefix("L3", "Argentina", "AR"),
    ItuPrefix("L4", "Argentina", "AR"),
    ItuPrefix("L5", "Argentina", "AR"),
    ItuPrefix("L6", "Argentina", "AR"),
    ItuPrefix("L7", "Argentina", "AR"),
    ItuPrefix("L8", "Argentina", "AR"),
    ItuPrefix("L9", "Argentina", "AR"),
    ItuPrefix("OA", "Peru", "PE"),
    ItuPrefix("OB", "Peru", "PE"),
    ItuPrefix("OC", "Peru", "PE"),
    ItuPrefix("OD", "Lebanon", "LB"),
    ItuPrefix("OE", "Austria", "AT"),
    ItuPrefix("OF", "Finland", "FI"),
    ItuPrefix("OG", "Finland", "FI"),
    ItuPrefix("OH", "Finland", "FI"),
    ItuPrefix("OI", "Finland", "FI"),
    ItuPrefix("OJ", "Finland", "FI"),
    ItuPrefix("OK", "Czech Republic", "CZ"),
    ItuPrefix("OL", "Czech Republic", "CZ"),
    ItuPrefix("OM", "Slovakia", "SK"),
    ItuPrefix("ON", "Belgium", "BE"),
    ItuPrefix("OO", "Belgium", "BE"),
    ItuPrefix("OP", "Belgium", "BE"),
    ItuPrefix("OQ", "Belgium", "BE"),
    ItuPrefix("OR", "Belgium", "BE"),
    ItuPrefix("OS", "Belgium", "BE"),
    ItuPrefix("OT", "Belgium", "BE"),
    ItuPrefix("OU", "Denmark", "DK"),
    ItuPrefix("OV", "Denmark", "DK"),
    ItuPrefix("OW", "Denmark", "DK"),
    ItuPrefix("OX", "Denmark", "DK"),
    ItuPrefix("OY", "Denmark", "DK"),
    ItuPrefix("OZ", "Denmark", "DK"),
    ItuPrefix("PA", "Netherlands", "NL"),
    ItuPrefix("PB", "Netherlands", "NL"),
    ItuPrefix("PC", "Netherlands", "NL"),
    ItuPrefix("PD", "Netherlands", "NL"),
    ItuPrefix("PE", "Netherlands", "NL"),
    ItuPrefix("PF", "Netherlands", "NL"),
    ItuPrefix("PG", "Netherlands", "NL"),
    ItuPrefix("PH", "Netherlands", "NL"),
    ItuPrefix("PI", "Netherlands", "NL"),
    ItuPrefix("PJ", "Netherlands", "NL"),
    ItuPrefix("PK", "Indonesia", "ID"),
    ItuPrefix("PL", "Indonesia", "ID"),
    ItuPrefix("PM", "Indonesia", "ID"),
    ItuPrefix("PN", "Indonesia", "ID"),
    ItuPrefix("PO", "Indonesia", "ID"),
    ItuPrefix("PP", "Brazil", "BR"),
    ItuPrefix("PQ", "Brazil", "BR"),
    ItuPrefix("PR", "Brazil", "BR"),
    ItuPrefix("PS", "Brazil", "BR"),
    ItuPrefix("PT", "Brazil", "BR"),
    ItuPrefix("PU", "Brazil", "BR"),
    ItuPrefix("PV", "Brazil", "BR"),
    ItuPrefix("PW", "Brazil", "BR"),
    ItuPrefix("PX", "Brazil", "BR"),
    ItuPrefix("PY", "Brazil", "BR"),
    ItuPrefix("PZ", "Suriname", "SR"),
    ItuPrefix("P2", "Papua New Guinea", "PG"),
    ItuPrefix("P3", "Cyprus", "CY"),
    ItuPrefix("P4", "Aruba", "AW"),
    ItuPrefix("P5", "North Korea", "KP"),
    ItuPrefix("P6", "North Korea", "KP"),
    ItuPrefix("P7", "North Korea", "KP"),
    ItuPrefix("P8", "North Korea", "KP"),
    ItuPrefix("P9", "North Korea", "KP"),
    ItuPrefix("SA", "Sweden", "SE"),
    ItuPrefix("SB", "Sweden", "SE"),
    ItuPrefix("SC", "Sweden", "SE"),
    ItuPrefix("SD", "Sweden", "SE"),
    ItuPrefix("SE", "Sweden", "SE"),
    ItuPrefix("SF", "Sweden", "SE"),
    ItuPrefix("SG", "Sweden", "SE"),
    ItuPrefix("SH", "Sweden", "SE"),
    ItuPrefix("SI", "Sweden", "SE"),
    ItuPrefix("SJ", "Sweden", "SE"),
    ItuPrefix("SK", "Sweden", "SE"),
    ItuPrefix("SL", "Sweden", "SE"),
    ItuPrefix("SM", "Sweden", "SE"),
    ItuPrefix("SN", "Poland", "PL"),
    ItuPrefix("SO", "Poland", "PL"),
    ItuPrefix("SP", "Poland", "PL"),
    ItuPrefix("SQ", "Poland", "PL"),
    ItuPrefix("SR", "Poland", "PL"),
    ItuPrefix("ST", "Sudan", "SD"),
    ItuPrefix("SU", "Egypt", "EG"),
    ItuPrefix("SV", "Greece", "GR"),
    ItuPrefix("SW", "Greece", "GR"),
    ItuPrefix("SX", "Greece", "GR"),
    ItuPrefix("SY", "Greece", "GR"),
    ItuPrefix("SZ", "Greece", "GR"),
    ItuPrefix("S2", "Bangladesh", "BD"),
    ItuPrefix("S3", "Bangladesh", "BD"),
    ItuPrefix("S5", "Slovenia", "SI"),
    ItuPrefix("S6", "Singapore", "SG"),
    ItuPrefix("S7", "Seychelles", "SC"),
    ItuPrefix("S8", "South Africa", "ZA"),
    ItuPrefix("S9", "Sao Tome and Principe", "ST"),
    ItuPrefix("TA", "Turkey", "TR"),
    ItuPrefix("TB", "Turkey", "TR"),
    ItuPrefix("TC", "Turkey", "TR"),
    ItuPrefix("TD", "Guatemala", "GT"),
    ItuPrefix("TE", "Costa Rica", "CR"),
    ItuPrefix("TF", "Iceland", "IS"),
    ItuPrefix("TG", "Guatemala", "GT"),
    ItuPrefix("TH", "France", "FR"),
    ItuPrefix("TI", "Costa Rica", "CR"),
    ItuPrefix("TJ", "Cameroon", "CM"),
    ItuPrefix("TK", "France", "FR"),
    ItuPrefix("TL", "Central African Republic", "CF"),
    ItuPrefix("TM", "France", "FR"),
    ItuPrefix("TN", "Congo", "CG"),
    ItuPrefix("TO", "France", "FR"),
    ItuPrefix("TP", "France", "FR"),
    ItuPrefix("TQ", "France", "FR"),
    ItuPrefix("TR", "Gabon", "GA"),
    ItuPrefix("TS", "Tunisia", "TN"),
    ItuPrefix("TT", "Chad", "TD"),
    ItuPrefix("TU", "Cote d'Ivoire", "CI"),
    ItuPrefix("TV", "France", "FR"),
    ItuPrefix("TW", "France", "FR"),
    ItuPrefix("TX", "France", "FR"),
    ItuPrefix("TY", "Benin", "BJ"),
    ItuPrefix("TZ", "Mali", "ML"),
    ItuPrefix("T2", "Tuvalu", "TV"),
    ItuPrefix("T3", "Kiribati", "KI"),
    ItuPrefix("T4", "Cuba", "CU"),
    ItuPrefix("T5", "Somalia", "SO"),
    ItuPrefix("T6", "Afghanistan", "AF"),
    ItuPrefix("T7", "San Marino", "SM"),
    ItuPrefix("T8", "Palau", "PW"),
    ItuPrefix("T9", "Bosnia-Herzegovina", "BA"),
    ItuPrefix("UA", "Russia", "RU"),
    ItuPrefix("UB", "Russia", "RU"),
    ItuPrefix("UC", "Russia", "RU"),
    ItuPrefix("UD", "Russia", "RU"),
    ItuPrefix("UE", "Russia", "RU"),
    ItuPrefix("UF", "Russia", "RU"),
    ItuPrefix("UG", "Russia", "RU"),
    ItuPrefix("UH", "Russia", "RU"),
    ItuPrefix("UI", "Russia", "RU"),
    ItuPrefix("UJ", "Uzbekistan", "UZ"),
    ItuPrefix("UK", "Uzbekistan", "UZ"),
    ItuPrefix("UL", "Uzbekistan", "UZ"),
    ItuPrefix("UM", "Uzbekistan", "UZ"),
    ItuPrefix("UN", "Kazakhstan", "KZ"),
    ItuPrefix("UO", "Kazakhstan", "KZ"),
    ItuPrefix("UP", "Kazakhstan", "KZ"),
    ItuPrefix("UQ", "Kazakhstan", "KZ"),
    ItuPrefix("UR", "Ukraine", "UA"),
    ItuPrefix("US", "Ukraine", "UA"),
    ItuPrefix("UT", "Ukraine", "UA"),
    ItuPrefix("UU", "Ukraine", "UA"),
    ItuPrefix("UV", "Ukraine", "UA"),
    ItuPrefix("UW", "Ukraine", "UA"),
    ItuPrefix("UX", "Ukraine", "UA"),
    ItuPrefix("UY", "Ukraine", "UA"),
    ItuPrefix("UZ", "Ukraine", "UA"),
    ItuPrefix("VA", "Canada", "CA"),
    ItuPrefix("VB", "Canada", "CA"),
    ItuPrefix("VC", "Canada", "CA"),
    ItuPrefix("VD", "Canada", "CA"),
    ItuPrefix("VE", "Canada", "CA"),
    ItuPrefix("VF", "Canada", "CA"),
    ItuPrefix("VG", "Canada", "CA"),
    ItuPrefix("VH", "Australia", "AU"),
    ItuPrefix("VI", "Australia", "AU"),
    ItuPrefix("VJ", "Australia", "AU"),
    ItuPrefix("VK", "Australia", "AU"),
    ItuPrefix("VL", "Australia", "AU"),
    ItuPrefix("VM", "Australia", "AU"),
    ItuPrefix("VN", "Australia", "AU"),
    ItuPrefix("VO", "Canada", "CA"),
    ItuPrefix("VP", "United Kingdom", "GB"),
    ItuPrefix("VQ", "United Kingdom", "GB"),
    ItuPrefix("VR", "Hong Kong", "HK"),
    ItuPrefix("VS", "United Kingdom", "GB"),
    ItuPrefix("VT", "India", "IN"),
    ItuPrefix("VU", "India", "IN"),
    ItuPrefix("VV", "India", "IN"),
    ItuPrefix("VW", "India", "IN"),
    ItuPrefix("VX", "Canada", "CA"),
    ItuPrefix("VY", "Canada", "CA"),
    ItuPrefix("VZ", "Australia", "AU"),
    ItuPrefix("V2", "Antigua and Barbuda", "AG"),
    ItuPrefix("V3", "Belize", "BZ"),
    ItuPrefix("V4", "Saint Kitts and Nevis", "KN"),
    ItuPrefix("V5", "Namibia", "NA"),
    ItuPrefix("V6", "Federated States of Micronesia", "FM"),
    ItuPrefix("V7", "Marshall Islands", "MH"),
    ItuPrefix("V8", "Brunei", "BN"),
    ItuPrefix("XA", "Mexico", "MX"),
    ItuPrefix("XB", "Mexico", "MX"),
    ItuPrefix("XC", "Mexico", "MX"),
    ItuPrefix("XD", "Mexico", "MX"),
    ItuPrefix("XE", "Mexico", "MX"),
    ItuPrefix("XF", "Mexico", "MX"),
    ItuPrefix("XG", "Mexico", "MX"),
    ItuPrefix("XH", "Mexico", "MX"),
    ItuPrefix("XI", "Mexico", "MX"),
    ItuPrefix("XJ", "Canada", "CA"),
    ItuPrefix("XK", "Canada", "CA"),
    ItuPrefix("XL", "Canada", "CA"),
    ItuPrefix("XM", "Canada", "CA"),
    ItuPrefix("XN", "Canada", "CA"),
    ItuPrefix("XO", "Canada", "CA"),
    ItuPrefix("XP", "Denmark", "DK"),
    ItuPrefix("XQ", "Chile", "CL"),
    ItuPrefix("XR", "Chile", "CL"),
    ItuPrefix("XS", "People's Republic of China", "CN"),
    ItuPrefix("XT", "Burkina Faso", "BF"),
    ItuPrefix("XU", "Cambodia", "KH"),
    ItuPrefix("XV", "Vietnam", "VN"),
    ItuPrefix("XW", "Laos", "LA"),
    ItuPrefix("XX", "Macao", "MO"),
    ItuPrefix("XY", "Myanmar", "MM"),
    ItuPrefix("XZ", "Myanmar", "MM"),
    ItuPrefix("YA", "Afghanistan", "AF"),
    ItuPrefix("YB", "Indonesia", "ID"),
    ItuPrefix("YC", "Indonesia", "ID"),
    ItuPrefix("YD", "Indonesia", "ID"),
    ItuPrefix("YE", "Indonesia", "ID"),
    ItuPrefix("YF", "Indonesia", "ID"),
    ItuPrefix("YG", "Indonesia", "ID"),
    ItuPrefix("YH", "Indonesia", "ID"),
    ItuPrefix("YI", "Iraq", "IQ"),
    ItuPrefix("YJ", "Vanuatu", "VU"),
    ItuPrefix("YK", "Syria", "SY"),
    ItuPrefix("YL", "Latvia", "LV"),
    ItuPrefix("YM", "Turkey", "TR"),
    ItuPrefix("YN", "Nicaragua", "NI"),
    ItuPrefix("YO", "Romania", "RO"),
    ItuPrefix("YP", "Romania", "RO"),
    ItuPrefix("YQ", "Romania", "RO"),
    ItuPrefix("YR", "Romania", "RO"),
    ItuPrefix("YS", "El Salvador", "SV"),
    ItuPrefix("YT", "Serbia", "RS"),
    ItuPrefix("YU", "Serbia", "RS"),
    ItuPrefix("YV", "Venezuela", "VE"),
    ItuPrefix("YW", "Venezuela", "VE"),
    ItuPrefix("YX", "Venezuela", "VE"),
    ItuPrefix("YY", "Venezuela", "VE"),
    ItuPrefix("Y2", "Germany", "DE"),
    ItuPrefix("Y3", "Germany", "DE"),
    ItuPrefix("Y4", "Germany", "DE"),
    ItuPrefix("Y5", "Germany", "DE"),
    ItuPrefix("Y6", "Germany", "DE"),
    ItuPrefix("Y7", "Germany", "DE"),
    ItuPrefix("Y8", "Germany", "DE"),
    ItuPrefix("Y9", "Germany", "DE"),
    ItuPrefix("ZA", "Albania", "AL"),
    ItuPrefix("ZB", "United Kingdom", "GB"),
    ItuPrefix("ZC", "United Kingdom", "GB"),
    ItuPrefix("ZD", "United Kingdom", "GB"),
    ItuPrefix("ZE", "United Kingdom", "GB"),
    ItuPrefix("ZF", "United Kingdom", "GB"),
    ItuPrefix("ZG", "United Kingdom", "GB"),
    ItuPrefix("ZH", "United Kingdom", "GB"),
    ItuPrefix("ZI", "United Kingdom", "GB"),
    ItuPrefix("ZJ", "United Kingdom", "GB"),
    ItuPrefix("ZK", "New Zealand", "NZ"),
    ItuPrefix("ZL", "New Zealand", "NZ"),
    ItuPrefix("ZM", "New Zealand", "NZ"),
    ItuPrefix("ZN", "United Kingdom", "GB"),
    ItuPrefix("ZO", "United Kingdom", "GB"),
    ItuPrefix("ZP", "Paraguay", "PY"),
    ItuPrefix("ZQ", "United Kingdom", "GB"),
    ItuPrefix("ZR", "South Africa", "ZA"),
    ItuPrefix("ZS", "South Africa", "ZA"),
    ItuPrefix("ZT", "South Africa", "ZA"),
    ItuPrefix("ZU", "South Africa", "ZA"),
    ItuPrefix("ZV", "Brazil", "BR"),
    ItuPrefix("ZW", "Brazil", "BR"),
    ItuPrefix("ZX", "Brazil", "BR"),
    ItuPrefix("ZY", "Brazil", "BR"),
    ItuPrefix("ZZ", "Brazil", "BR"),
    ItuPrefix("Z2", "Zimbabwe", "ZW"),
    ItuPrefix("Z3", "North Macedonia", "MK"),
    ItuPrefix("Z8", "South Sudan", "SS"),
    ItuPrefix("3A", "Monaco", "MC"),
    ItuPrefix("3B", "Mauritius", "MU"),
    ItuPrefix("3C", "Equatorial Guinea", "GQ"),
    ItuPrefix("3E", "Panama", "PA"),
    ItuPrefix("3F", "Panama", "PA"),
    ItuPrefix("3G", "Chile", "CL"),
    ItuPrefix("3H", "People's Republic of China", "CN"),
    ItuPrefix("3I", "People's Republic of China", "CN"),
    ItuPrefix("3J", "People's Republic of China", "CN"),
    ItuPrefix("3K", "People's Republic of China", "CN"),
    ItuPrefix("3L", "People's Republic of China", "CN"),
    ItuPrefix("3M", "People's Republic of China", "CN"),
    ItuPrefix("3N", "People's Republic of China", "CN"),
    ItuPrefix("3O", "People's Republic of China", "CN"),
    ItuPrefix("3P", "People's Republic of China", "CN"),
    ItuPrefix("3Q", "People's Republic of China", "CN"),
    ItuPrefix("3R", "People's Republic of China", "CN"),
    ItuPrefix("3S", "People's Republic of China", "CN"),
    ItuPrefix("3T", "People's Republic of China", "CN"),
    ItuPrefix("3U", "People's Republic of China", "CN"),
    ItuPrefix("3V", "Tunisia", "TN"),
    ItuPrefix("3W", "Vietnam", "VN"),
    ItuPrefix("3X", "Guinea", "GN"),
    ItuPrefix("3Y", "Norway", "NO"),
    ItuPrefix("3Z", "Poland", "PL"),
    ItuPrefix("4A", "Mexico", "MX"),
    ItuPrefix("4B", "Mexico", "MX"),
    ItuPrefix("4C", "Mexico", "MX"),
    ItuPrefix("4D", "Philippines", "PH"),
    ItuPrefix("4E", "Philippines", "PH"),
    ItuPrefix("4F", "Philippines", "PH"),
    ItuPrefix("4G", "Philippines", "PH"),
    ItuPrefix("4H", "Philippines", "PH"),
    ItuPrefix("4I", "Philippines", "PH"),
    ItuPrefix("4J", "Azerbaijan", "AZ"),
    ItuPrefix("4K", "Azerbaijan", "AZ"),
    ItuPrefix("4L", "Georgia", "GE"),
    ItuPrefix("4M", "Venezuela", "VE"),
    ItuPrefix("4O", "Montenegro", "ME"),
    ItuPrefix("4P", "Sri Lanka", "LK"),
    ItuPrefix("4Q", "Sri Lanka", "LK"),
    ItuPrefix("4R", "Sri Lanka", "LK"),
    ItuPrefix("4S", "Sri Lanka", "LK"),
    ItuPrefix("4T", "Peru", "PE"),
    ItuPrefix("4U", "United Nations", None),
    ItuPrefix("4V", "Haiti", "HT"),
    ItuPrefix("4W", "East Timor", "TL"),
    ItuPrefix("4X", "Israel", "IL"),
    ItuPrefix("4Y", "International Civil Aviation Organization", None),
    ItuPrefix("4Z", "Israel", "IL"),
    ItuPrefix("5A", "Libya", "LY"),
    ItuPrefix("5B", "Cyprus", "CY"),
    ItuPrefix("5C", "Morocco", "MA"),
    ItuPrefix("5D", "Morocco", "MA"),
    ItuPrefix("5E", "Morocco", "MA"),
    ItuPrefix("5F", "Morocco", "MA"),
    ItuPrefix("5G", "Morocco", "MA"),
    ItuPrefix("5H", "Tanzania", "TZ"),
    ItuPrefix("5I", "Tanzania", "TZ"),
    ItuPrefix("5J", "Colombia", "CO"),
    ItuPrefix("5K", "Colombia", "CO"),
    ItuPrefix("5L", "Liberia", "LR"),
    ItuPrefix("5M", "Liberia", "LR"),
    ItuPrefix("5N", "Nigeria", "NG"),
    ItuPrefix("5O", "Nigeria", "NG"),
    ItuPrefix("5P", "Denmark", "DK"),
    ItuPrefix("5Q", "Denmark", "DK"),
    ItuPrefix("5R", "Madagascar", "MG"),
    ItuPrefix("5S", "Madagascar", "MG"),
    ItuPrefix("5T", "Mauritania", "MR"),
    ItuPrefix("5U", "Niger", "NG"),
    ItuPrefix("5V", "Togo", "TG"),
    ItuPrefix("5W", "Western Samoa", "WS"),
    ItuPrefix("5X", "Uganda", "UG"),
    ItuPrefix("5Y", "Kenya", "KE"),
    ItuPrefix("5Z", "Kenya", "KE"),
    ItuPrefix("6A", "Egypt", "EG"),
    ItuPrefix("6B", "Egypt", "EG"),
    ItuPrefix("6C", "Syria", "SY"),
    ItuPrefix("6D", "Mexico", "MX"),
    ItuPrefix("6E", "Mexico", "MX"),
    ItuPrefix("6F", "Mexico", "MX"),
    ItuPrefix("6G", "Mexico", "MX"),
    ItuPrefix("6H", "Mexico", "MX"),
    ItuPrefix("6I", "Mexico", "MX"),
    ItuPrefix("6J", "Mexico", "MX"),
    ItuPrefix("6K", "South Korea", "KR"),
    ItuPrefix("6L", "South Korea", "KR"),
    ItuPrefix("6M", "South Korea", "KR"),
    ItuPrefix("6N", "South Korea", "KR"),
    ItuPrefix("6O", "Somalia", "SO"),
    ItuPrefix("6P", "Pakistan", "PK"),
    ItuPrefix("6Q", "Pakistan", "PK"),
    ItuPrefix("6R", "Pakistan", "PK"),
    ItuPrefix("6S", "Pakistan", "PK"),
    ItuPrefix("6T", "Sudan", "SD"),
    ItuPrefix("6U", "Sudan", "SD"),
    ItuPrefix("6V", "Senegal", "SN"),
    ItuPrefix("6W", "Senegal", "SN"),
    ItuPrefix("6X", "Madagascar", "MG"),
    ItuPrefix("6Y", "Jamaica", "JM"),
    ItuPrefix("6Z", "Liberia", "LR"),
    ItuPrefix("7A", "Indonesia", "ID"),
    ItuPrefix("7B", "Indonesia", "ID"),
    ItuPrefix("7C", "Indonesia", "ID"),
    ItuPrefix("7D", "Indonesia", "ID"),
    ItuPrefix("7E", "Indonesia", "ID"),
    ItuPrefix("7F", "Indonesia", "ID"),
    ItuPrefix("7G", "Indonesia", "ID"),
    ItuPrefix("7H", "Indonesia", "ID"),
    ItuPrefix("7I", "Indonesia", "ID"),
    ItuPrefix("7J", "Japan", "JP"),
    ItuPrefix("7K", "Japan", "JP"),
    ItuPrefix("7L", "Japan", "JP"),
    ItuPrefix("7M", "Japan", "JP"),
    ItuPrefix("7N", "Japan", "JP"),
    ItuPrefix("7O", "Yemen", "YE"),
    ItuPrefix("7P", "Lesotho", "LS"),
    ItuPrefix("7Q", "Malawi", "MW"),
    ItuPrefix("7R", "Algeria", "DZ"),
    ItuPrefix("7S", "Sweden", "SE"),
    ItuPrefix("7T", "Algeria", "DZ"),
    ItuPrefix("7U", "Algeria", "DZ"),
    ItuPrefix("7V", "Algeria", "DZ"),
    ItuPrefix("7W", "Algeria", "DZ"),
    ItuPrefix("7X", "Algeria", "DZ"),
    ItuPrefix("7Y", "Algeria", "DZ"),
    ItuPrefix("7Z", "Saudi Arabia", "SA"),
    ItuPrefix("8A", "Indonesia", "ID"),
    ItuPrefix("8B", "Indonesia", "ID"),
    ItuPrefix("8C", "Indonesia", "ID"),
    ItuPrefix("8D", "Indonesia", "ID"),
    ItuPrefix("8E", "Indonesia", "ID"),
    ItuPrefix("8F", "Indonesia", "ID"),
    ItuPrefix("8G", "Indonesia", "ID"),
    ItuPrefix("8H", "Indonesia", "ID"),
    ItuPrefix("8I", "Indonesia", "ID"),
    ItuPrefix("8J", "Japan", "JP"),
    ItuPrefix("8K", "Japan", "JP"),
    ItuPrefix("8L", "Japan", "JP"),
    ItuPrefix("8M", "Japan", "JP"),
    ItuPrefix("8N", "Japan", "JP"),
    ItuPrefix("8O", "Botswana", "BW"),
    ItuPrefix("8P", "Barbados", "BB"),
    ItuPrefix("8Q", "Maldives", "MV"),
    ItuPrefix("8R", "Guyana", "GY"),
    ItuPrefix("8S", "Sweden", "SE"),
    ItuPrefix("8T", "India", "IN"),
    ItuPrefix("8U", "India", "IN"),
    ItuPrefix("8V", "India", "IN"),
    ItuPrefix("8W", "India", "IN"),
    ItuPrefix("8X", "India", "IN"),
    ItuPrefix("8Y", "India", "IN"),
    ItuPrefix("8Z", "Saudi Arabia", "SA"),
    ItuPrefix("9A", "Croatia", "HR"),
    ItuPrefix("9B", "Iran", "IR"),
    ItuPrefix("9C", "Iran", "IR"),
    ItuPrefix("9D", "Iran", "IR"),
    ItuPrefix("9E", "Ethiopia", "ET"),
    ItuPrefix("9F", "Ethiopia", "ET"),
    ItuPrefix("9G", "Ghana", "GH"),
    ItuPrefix("9H", "Malta", "MT"),
    ItuPrefix("9I", "Zambia", "ZM"),
    ItuPrefix("9J", "Zambia", "ZM"),
    ItuPrefix("9K", "Kuwait", "KW"),
    ItuPrefix("9L", "Sierra Leone", "SL"),
    ItuPrefix("9M", "Malaysia", "MY"),
    ItuPrefix("9N", "Nepal", "NP"),
    ItuPrefix("9O", "Democratic Republic of the Congo", "CG"),
    ItuPrefix("9P", "Democratic Republic of the Congo", "CG"),
    ItuPrefix("9Q", "Democratic Republic of the Congo", "CG"),
    ItuPrefix("9R", "Democratic Republic of the Congo", "CG"),
    ItuPrefix("9S", "Democratic Republic of the Congo", "CG"),
    ItuPrefix("9T", "Democratic Republic of the Congo", "CG"),
    ItuPrefix("9U", "Burundi", "BI"),
    ItuPrefix("9V", "Singapore", "SG"),
    ItuPrefix("9W", "Malaysia", "MY"),
    ItuPrefix("9X", "Rwanda", "RW"),
    ItuPrefix("9Y", "Trinidad and Tobago", "TT"),
    ItuPrefix("9Z", "Trinidad and Tobago", "TT"),
    ItuPrefix("B", "China", "CN"),
    ItuPrefix("F", "France", "FR"),
    ItuPrefix("G", "United Kingdom", "GB"),
    ItuPrefix("I", "Italy", "IT"),
    ItuPrefix("K", "United States", "US"),
    ItuPrefix("M", "United Kingdom", "GB"),
    ItuPrefix("N", "United States", "US"),
    ItuPrefix("R", "Russia", "RU"),
    ItuPrefix("W", "United States", "US"),
    ItuPrefix("2", "United Kingdom", "GB"),
]


def call_sign_to_country(call_sign: str) -> ItuPrefix | None:
    """
    Determine which country likely issued a given call sign.
    Returns an ITU_Prefix record, or None (if no match was found)
    """
    call_sign = call_sign.strip().upper()
    for record in ITU_PREFIXES:
        if call_sign.startswith(record.prefix):
            return record
    return None


def prefix_to_countries(prefix: str) -> List[ItuPrefix]:
    """
    Given a prefix, determine which country or countries might issue
    call signs starting with that prefix. For "A" could be the
    United States, Spain, Pakistan, etc. Whereas "K" is just the United
    States, and "CF" is Canada.
    Returns a list of ITU_Prefix records.
    """
    results: List[ITU_Prefix] = []
    prefix = prefix.strip().upper()
    if len(prefix) < 1 or len(prefix) > 4:
        raise ValueError("Prefixes sould be 0-4 character.")
    for record in ITU_PREFIXES:
        if prefix.startswith(record.prefix) or record.prefix.startswith(prefix):
            results.append(record)
    return results


def country_to_prefixes(country_code: str) -> List[ItuPrefix]:
    """
    Given an ISO 3166-1 alpha-2 (two letter) country code, determine which
    ITU prefixes that country might use for call signs. For example the "US"
    could issue call signs beginning with "AA-AL", "K", "N", or "W".
    Returns a list of ITU_Prefix records.
    """
    results: List[ITU_Prefix] = []
    country_code = country_code.strip()
    if len(country_code) != 2:
        raise ValueError(
            "'{country_code}' sould be a ISO 3166-1 alpha-2 (two letter) country code."
        )
    country_code = country_code.upper()
    for record in ITU_PREFIXES:
        if record.country_code == country_code:
            results.append(record)
    return results
