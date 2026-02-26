--
-- PostgreSQL database dump
--

-- Dumped from database version 15.8
-- Dumped by pg_dump version 17.4

--
-- Name: appointmentservicegrouptype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.appointmentservicegrouptype AS ENUM (
    'NO_DETAIL',
    'SINGLE',
    'MULTIPLE'
);


--
-- Name: appointmentstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.appointmentstatus AS ENUM (
    'PREPAYMENT',
    'PAYMENT_STARTED',
    'CONFIRMED',
    'CANCELLED',
    'MISSED',
    'COMPLETED'
);


--
-- Name: branchtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.branchtype AS ENUM (
    'MAIN',
    'ONSITE'
);


--
-- Name: collectionmethod; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.collectionmethod AS ENUM (
    'WALKIN',
    'DELIVERY',
    'PICKUP'
);


--
-- Name: contentcategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.contentcategory AS ENUM (
    'TERMS_AND_CONDITIONS',
    'HOME_BANNER',
    'ABOUT_US',
    'FAQ',
    'FAQ_SECTION',
    'PRIVACY_POLICY'
);


--
-- Name: corpauthorisation; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.corpauthorisation AS ENUM (
    'BLOCK_EDOCS'
);


--
-- Name: dayofweek; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.dayofweek AS ENUM (
    'MONDAY',
    'TUESDAY',
    'WEDNESDAY',
    'THURSDAY',
    'FRIDAY',
    'SATURDAY',
    'SUNDAY',
    'PUBLIC_HOLIDAY'
);


--
-- Name: documentstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.documentstatus AS ENUM (
    'VOID',
    'DRAFT',
    'PENDING',
    'COMPLETE',
    'APP_HEALTH_REPORT'
);


--
-- Name: documenttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.documenttype AS ENUM (
    'INVOICE',
    'MC',
    'HEALTH_SCREENING',
    'LAB',
    'RADIOLOGY',
    'REFERRAL_LETTER',
    'VACCINATION'
);


--
-- Name: firebaselogintype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.firebaselogintype AS ENUM (
    'PHONE',
    'EMAIL'
);


--
-- Name: patienttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.patienttype AS ENUM (
    'PRIVATE_PATIENT',
    'MIGRANT_WORKER'
);


--
-- Name: paymentmethod; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paymentmethod AS ENUM (
    'NETS_CLICK',
    'CARD_STRIPE',
    'CARD_SGIMED',
    'CARD_2C2P',
    'PAYNOW_NETS',
    'PAYNOW_STRIPE',
    'PAYNOW_2C2P',
    'DEFERRED_PAYMENT'
);


--
-- Name: paymentprovider; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paymentprovider AS ENUM (
    'APP_STRIPE',
    'APP_NETS_CLICK',
    'APP_2C2P'
);


--
-- Name: paymentstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paymentstatus AS ENUM (
    'PAYMENT_CREATED',
    'PAYMENT_CANCELED',
    'PAYMENT_EXPIRED',
    'PAYMENT_FAILED',
    'PAYMENT_SUCCESS'
);


--
-- Name: paymenttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.paymenttype AS ENUM (
    'PREPAYMENT',
    'POSTPAYMENT',
    'APPOINTMENT',
    'TOKENIZATION'
);


--
-- Name: phonecountrycode; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.phonecountrycode AS ENUM (
    'UK',
    'USA',
    'ALGERIA',
    'ANDORRA',
    'ANGOLA',
    'ANGUILLA',
    'ANTIGUABARBUDA',
    'ARGENTINA',
    'ARMENIA',
    'ARUBA',
    'AUSTRALIA',
    'AUSTRIA',
    'AZERBAIJAN',
    'BAHAMAS',
    'BAHRAIN',
    'BANGLADESH',
    'BARBADOS',
    'BELARUS',
    'BELGIUM',
    'BELIZE',
    'BENIN',
    'BERMUDA',
    'BHUTAN',
    'BOLIVIA',
    'BOSNIAHERZEGOVINA',
    'BOTSWANA',
    'BRAZIL',
    'BRUNEI',
    'BULGARIA',
    'BURKINAFASO',
    'BURUNDI',
    'CAMBODIA',
    'CAMEROON',
    'CAPEVERDEISLANDS',
    'CAYMANISLANDS',
    'CENTRALAFRICANREPUBLIC',
    'CHILE',
    'CHINA',
    'COLOMBIA',
    'COMOROS',
    'CONGO',
    'COOKISLANDS',
    'COSTARICA',
    'CROATIA',
    'CUBA',
    'CYPRUSNORTH',
    'CYPRUSSOUTH',
    'CZECHREPUBLIC',
    'DENMARK',
    'DJIBOUTI',
    'DOMINICA',
    'ECUADOR',
    'EGYPT',
    'ELSALVADOR',
    'EQUATORIALGUINEA',
    'ERITREA',
    'ESTONIA',
    'ETHIOPIA',
    'FALKLANDISLANDS',
    'FAROEISLANDS',
    'FIJI',
    'FINLAND',
    'FRANCE',
    'FRENCHGUIANA',
    'FRENCHPOLYNESIA',
    'GABON',
    'GAMBIA',
    'GEORGIA',
    'GERMANY',
    'GHANA',
    'GIBRALTAR',
    'GREECE',
    'GREENLAND',
    'GRENADA',
    'GUADELOUPE',
    'GUAM',
    'GUATEMALA',
    'GUINEA',
    'GUINEABISSAU',
    'GUYANA',
    'HAITI',
    'HONDURAS',
    'HONGKONG',
    'HUNGARY',
    'ICELAND',
    'INDIA',
    'INDONESIA',
    'IRAN',
    'IRAQ',
    'IRELAND',
    'ISRAEL',
    'ITALY',
    'JAMAICA',
    'JAPAN',
    'JORDAN',
    'KAZAKHSTAN',
    'KENYA',
    'KIRIBATI',
    'KOREANORTH',
    'KOREASOUTH',
    'KUWAIT',
    'KYRGYZSTAN',
    'LAOS',
    'LATVIA',
    'LEBANON',
    'LESOTHO',
    'LIBERIA',
    'LIBYA',
    'LIECHTENSTEIN',
    'LITHUANIA',
    'LUXEMBOURG',
    'MACAO',
    'MACEDONIA',
    'MADAGASCAR',
    'MALAWI',
    'MALAYSIA',
    'MALDIVES',
    'MALI',
    'MALTA',
    'MARSHALLISLANDS',
    'MARTINIQUE',
    'MAURITANIA',
    'MAURITIUS',
    'MEXICO',
    'MICRONESIA',
    'MOLDOVA',
    'MONACO',
    'MONGOLIA',
    'MONTSERRAT',
    'MOROCCO',
    'MOZAMBIQUE',
    'MYANMAR',
    'NAMIBIA',
    'NAURU',
    'NEPAL',
    'NETHERLANDS',
    'NEWCALEDONIA',
    'NEWZEALAND',
    'NICARAGUA',
    'NIGER',
    'NIGERIA',
    'NIUE',
    'NORFOLKISLANDS',
    'NORTHERNMARIANAS',
    'NORWAY',
    'OMAN',
    'PALAU',
    'PANAMA',
    'PAPUANEWGUINEA',
    'PARAGUAY',
    'PERU',
    'PHILIPPINES',
    'POLAND',
    'PORTUGAL',
    'PUERTORICO',
    'QATAR',
    'REUNION',
    'ROMANIA',
    'RWANDA',
    'SANMARINO',
    'SAOTOMEPRINCIPE',
    'SAUDIARABIA',
    'SENEGAL',
    'SERBIA',
    'SEYCHELLES',
    'SIERRALEONE',
    'SINGAPORE',
    'SLOVAKREPUBLIC',
    'SLOVENIA',
    'SOLOMONISLANDS',
    'SOMALIA',
    'SOUTHAFRICA',
    'SPAIN',
    'SRILANKA',
    'STHELENA',
    'STKITTS',
    'STLUCIA',
    'SUDAN',
    'SURINAME',
    'SWAZILAND',
    'SWEDEN',
    'SWITZERLAND',
    'SYRIA',
    'TAIWAN',
    'THAILAND',
    'TOGO',
    'TONGA',
    'TRINIDADTOBAGO',
    'TUNISIA',
    'TURKEY',
    'TURKMENISTANB',
    'TURKSCAICOSISLANDS',
    'TUVALU',
    'UGANDA',
    'UKRAINE',
    'UNITEDARABEMIRATES',
    'URUGUAY',
    'VANUATU',
    'VATICANCITY',
    'VENEZUELA',
    'VIETNAM',
    'VIRGINISLANDSBRITISH',
    'VIRGINISLANDSUS',
    'WALLISFUTUNA',
    'YEMENNORTH',
    'YEMENSOUTH',
    'ZAMBIA',
    'ZIMBABWE'
);


--
-- Name: role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.role AS ENUM (
    'SUPERADMIN',
    'ADMIN',
    'DOCTOR'
);


--
-- Name: sgimedgender; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sgimedgender AS ENUM (
    'MALE',
    'FEMALE',
    'UNKNOWN'
);


--
-- Name: sgimedictype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sgimedictype AS ENUM (
    'PINK_IC',
    'BLUE_IC',
    'FIN_NUMBER',
    'PASSPORT'
);


--
-- Name: sgimedlanguage; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sgimedlanguage AS ENUM (
    'ENGLISH',
    'AKAN',
    'ALBANIAN',
    'AMHARIC',
    'ANNAMESE',
    'ARABIC',
    'ARMENIAN',
    'ASSAMESE',
    'AZERBAIJANI',
    'BANGLA',
    'BANJARESE',
    'BATAK',
    'BAUAN',
    'BENGALI',
    'BHUTANESE',
    'BOYANESE',
    'BUGIS',
    'BULGARIAN',
    'BURMESE',
    'CAMBODIAN',
    'CANTONESE',
    'CHALDEAN',
    'CHAWAN',
    'CHEKIANG',
    'CREOLE',
    'CROATIAN',
    'CZECH',
    'DANISH',
    'DAYAK',
    'DUSUN',
    'DUTCH',
    'FARSI',
    'FILIPINO',
    'FINNISH',
    'FLEMISH',
    'FOOCHOW',
    'FRENCH',
    'GERMAN',
    'GHANAIAN',
    'GOANESE',
    'GREEK',
    'GUJARATI',
    'GURKHALI',
    'HAINANESE',
    'HAKKA',
    'HEBREW',
    'HENGHUA',
    'HINDI',
    'HINDUSTANI',
    'HOCKCHIA',
    'HOKKIEN',
    'HUBEI',
    'HUNAN',
    'HUNGARIAN',
    'IBAN',
    'ICELANDIC',
    'ILOCANO',
    'ILONGO',
    'INDONESIAN',
    'IRISH',
    'ITALIAN',
    'JAFFNESE',
    'JAPANESE',
    'JAVANESE',
    'KADAZAN',
    'KANNADA',
    'KAREN',
    'KASHMIRI',
    'KAYAN',
    'KELABIT',
    'KHASI',
    'KHEK',
    'KHMER',
    'KIANGSI',
    'KIKUYU',
    'KONKANI',
    'KOREAN',
    'KWONGSAI',
    'LAO',
    'LITHUANIAN',
    'LUICHEW',
    'MALABARI',
    'MALAGASY',
    'MALAY',
    'MALAYALAM',
    'MALDIVIAN',
    'MALTESE',
    'MANCHU',
    'MANDARIN',
    'MANDINGO',
    'MAORI',
    'MARATHI',
    'MELANAU',
    'MINANGKABAU',
    'MONGOLIAN',
    'MONTENEGRIN',
    'MULTANI',
    'MYANMAR',
    'NEPALESE',
    'NEPALI',
    'NEWARI',
    'NORWEGIAN',
    'ORIYA',
    'OTHERS',
    'PAMPANGAN',
    'PATHAN',
    'PEKINESE',
    'PERSIAN',
    'POLISH',
    'PORTUGUESE',
    'PUNJABI',
    'PUSHTU',
    'RAKHINE',
    'ROMANIAN',
    'RUSSIAN',
    'SCOTTISH',
    'SERBIAN',
    'SHAN',
    'SHANGHAINESE',
    'SHANSI',
    'SHANTUNG',
    'SINDHI',
    'SINHALESE',
    'SLAVIC',
    'SLOVAK',
    'SPANISH',
    'SUNDANESE',
    'SWEDISH',
    'SWISS_GERMAN',
    'SZECHUAN',
    'TAGALOG',
    'TAIWANESE',
    'TAMIL',
    'TELUGU',
    'TEOCHEW',
    'THAI',
    'TIBETAN',
    'TONGAN',
    'TURKISH',
    'UNKNOWN',
    'URDU',
    'VIETNAMESE',
    'VISAYAN',
    'WELSH',
    'WENCHOW',
    'YIDDISH'
);


--
-- Name: sgimedmaritalstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sgimedmaritalstatus AS ENUM (
    'SINGLE',
    'MARRIED',
    'DIVORCED',
    'WIDOWED',
    'SEPARATED',
    'NOT_REPORTED'
);


--
-- Name: sgimednationality; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sgimednationality AS ENUM (
    'SINGAPORE_CITIZEN',
    'AFGHAN',
    'ALBANIAN',
    'ALGERIAN',
    'AMERICAN',
    'ANDORRAN',
    'ANGOLAN',
    'ANTIGUAN',
    'ARGENTINIAN',
    'ARMENIAN',
    'AUSTRALIAN',
    'AUSTRIAN',
    'AZERBAIJANI',
    'BAHAMIAN',
    'BAHRAINI',
    'BANGLADESHI',
    'BARBADOS',
    'BELARUSSIAN',
    'BELGIAN',
    'BELIZEAN',
    'BENINESE',
    'BHUTANESE',
    'BOLIVIAN',
    'BOSNIAN',
    'BOTSWANA',
    'BRAZILIAN',
    'BRITISH',
    'BRITISH_NATIONAL_OVERSEAS',
    'BRITISH_OVERSEAS_CITIZEN',
    'BRITISH_OVERSEAS_TERRITORIES_CITIZEN',
    'BRITISH_PROTECTED_PERSON',
    'BRITISH_SUBJECT',
    'BRUNEIAN',
    'BULGARIAN',
    'BURKINABE',
    'BURUNDIAN',
    'CAMBODIAN',
    'CAMEROONIAN',
    'CANADIAN',
    'CAPE_VERDEAN',
    'CENTRAL_AFRICAN_REPUBLIC',
    'CHADIAN',
    'CHILEAN',
    'CHINESE',
    'COLOMBIAN',
    'COMORAN',
    'CONGOLESE',
    'COSTA_RICAN',
    'CROATIAN',
    'CUBAN',
    'CYPRIOT',
    'CZECH',
    'DANISH',
    'DEMOCRATIC_REPUBLIC_OF_THE_CONGO',
    'DJIBOUTIAN',
    'DOMINICAN',
    'DOMINICAN_REPUBLIC',
    'EAST_TIMORESE',
    'ECUADORIAN',
    'EGYPTIAN',
    'EQUATORIAL_GUINEA',
    'ERITREAN',
    'ESTONIAN',
    'ETHIOPIAN',
    'FIJIAN',
    'FILIPINO',
    'FINNISH',
    'FRENCH',
    'GABON',
    'GAMBIAN',
    'GEORGIAN',
    'GERMAN',
    'GHANAIAN',
    'GREEK',
    'GRENADIAN',
    'GUATEMALAN',
    'GUINEAN',
    'GUINEAN_BISSAU',
    'GUYANESE',
    'HAITIAN',
    'HONDURAN',
    'HONG_KONG',
    'HUNGARIAN',
    'ICELANDER',
    'INDIAN',
    'INDONESIAN',
    'IRANIAN',
    'IRAQI',
    'IRISH',
    'ISRAELI',
    'ITALIAN',
    'IVORY_COAST',
    'JAMAICAN',
    'JAPANESE',
    'JORDANIAN',
    'KAZAKHSTANI',
    'KENYAN',
    'KIRIBATI',
    'KITTIAN_AND_NEVISIAN',
    'KOREAN_NORTH',
    'KOREAN_SOUTH',
    'KUWAITI',
    'KYRGYZSTAN',
    'LAOTIAN',
    'LATVIAN',
    'LEBANESE',
    'LESOTHO',
    'LIBERIAN',
    'LIBYAN',
    'LIECHTENSTEINER',
    'LITHUANIAN',
    'LUXEMBOURGER',
    'MACAO',
    'MACEDONIAN',
    'MADAGASY',
    'MALAWIAN',
    'MALAYSIAN',
    'MALDIVIAN',
    'MALIAN',
    'MALTESE',
    'MARSHALLESE',
    'MAURITANEAN',
    'MAURITIAN',
    'MEXICAN',
    'MICRONESIAN',
    'MOLDAVIAN',
    'MONACAN',
    'MONGOLIAN',
    'MONTENEGRIN',
    'MOROCCAN',
    'MOZAMBICAN',
    'MYANMAR',
    'NAMIBIAN',
    'NAURUAN',
    'NEPALESE',
    'NETHERLANDS',
    'NEW_ZEALANDER',
    'NIVANUATU',
    'NICARAGUAN',
    'NIGER',
    'NIGERIAN',
    'NORWEGIAN',
    'OMANI',
    'PAKISTANI',
    'PALAUAN',
    'PALESTINIAN',
    'PANAMANIAN',
    'PAPUA_NEW_GUINEAN',
    'PARAGUAYAN',
    'PERUVIAN',
    'POLISH',
    'PORTUGUESE',
    'QATARI',
    'REFUGEE_OTHER_THAN_XXB',
    'REFUGEE_XXB',
    'ROMANIAN',
    'RUSSIAN',
    'RWANDAN',
    'SALVADORAN',
    'SAMMARINESE',
    'SAMOAN',
    'SAO_TOMEAN',
    'SAUDI_ARABIAN',
    'SENEGALESE',
    'SERBIAN',
    'SEYCHELLOIS',
    'SIERRA_LEONE',
    'SLOVAK',
    'SLOVENIAN',
    'SOLOMON_ISLANDER',
    'SOMALI',
    'SOUTH_AFRICAN',
    'SPANISH',
    'SRI_LANKAN',
    'ST_LUCIA',
    'ST_VINCENTIAN',
    'STATELESS',
    'SUDANESE',
    'SURINAMER',
    'SWAZI',
    'SWEDISH',
    'SWISS',
    'SYRIAN',
    'TAIWANESE',
    'TAJIKISTANI',
    'TANZANIAN',
    'THAI',
    'TOGOLESE',
    'TONGAN',
    'TRINIDADIAN_AND_TOBAGONIAN',
    'TUNISIAN',
    'TURK',
    'TURKMEN',
    'TUVALU',
    'UGANDAN',
    'UKRAINIAN',
    'UNITED_ARAB_EMIRATES',
    'UNKNOWN',
    'URUGUAYAN',
    'UZBEKISTAN',
    'VATICAN_CITY_STATE_HOLY_SEE',
    'VENEZUELAN',
    'VIETNAMESE',
    'YEMENI',
    'ZAMBIAN',
    'ZIMBABWEAN'
);


--
-- Name: sgimednokrelation; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sgimednokrelation AS ENUM (
    'SPOUSE',
    'CHILDREN',
    'PARENT',
    'GRANDPARENT',
    'IN_LAWS',
    'SIBLINGS',
    'GUARDIAN',
    'OTHER'
);


--
-- Name: teleconsultstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.teleconsultstatus AS ENUM (
    'PREPAYMENT',
    'CHECKED_IN',
    'CONSULT_START',
    'CONSULT_END',
    'OUTSTANDING',
    'DISPENSE_MEDICATION',
    'CHECKED_OUT',
    'CANCELLED',
    'MISSED'
);


--
-- Name: visittype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.visittype AS ENUM (
    'TELECONSULT',
    'WALKIN',
    'APPOINTMENT'
);


--
-- Name: walkinqueuestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.walkinqueuestatus AS ENUM (
    'PENDING',
    'REJECTED',
    'CHECKED_IN',
    'CONSULT_START',
    'CANCELLED',
    'MISSED',
    'CHECKED_OUT'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

-- CREATE TABLE public.alembic_version (
--     version_num character varying(32) NOT NULL
-- );


--
-- Name: appointment_corporate_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointment_corporate_codes (
    id uuid NOT NULL,
    code character varying NOT NULL,
    organization character varying NOT NULL,
    valid_from timestamp with time zone,
    valid_to timestamp with time zone,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: appointment_counts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointment_counts (
    id integer NOT NULL,
    sgimed_branch_id character varying NOT NULL,
    sgimed_calendar_id character varying NOT NULL,
    "time" timestamp with time zone NOT NULL,
    count integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: appointment_counts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.appointment_counts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: appointment_counts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.appointment_counts_id_seq OWNED BY public.appointment_counts.id;


--
-- Name: appointment_onsite_branches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointment_onsite_branches (
    id integer NOT NULL,
    branch_id uuid NOT NULL,
    corporate_code_id uuid,
    header character varying,
    start_date timestamp with time zone NOT NULL,
    end_date timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: appointment_onsite_branches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.appointment_onsite_branches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: appointment_onsite_branches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.appointment_onsite_branches_id_seq OWNED BY public.appointment_onsite_branches.id;


--
-- Name: appointment_operating_hours; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointment_operating_hours (
    id uuid NOT NULL,
    day public.dayofweek NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    cutoff_time integer NOT NULL,
    max_bookings integer NOT NULL,
    branch_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: appointment_service_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointment_service_groups (
    id uuid NOT NULL,
    name character varying NOT NULL,
    description character varying,
    index integer NOT NULL,
    icon character varying NOT NULL,
    duration integer NOT NULL,
    type public.appointmentservicegrouptype NOT NULL,
    restricted_branches character varying[] NOT NULL,
    corporate_code_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: appointment_services; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.appointment_services (
    id uuid NOT NULL,
    name character varying NOT NULL,
    price double precision,
    index integer NOT NULL,
    min_booking_ahead_days integer NOT NULL,
    group_id uuid NOT NULL,
    restricted_branches character varying[] NOT NULL,
    tests json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: backend_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.backend_configs (
    key character varying NOT NULL,
    value character varying NOT NULL,
    value_type character varying NOT NULL,
    description character varying,
    category character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: backend_crons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.backend_crons (
    id character varying NOT NULL,
    last_modified timestamp without time zone NOT NULL,
    last_page integer
);


--
-- Name: backend_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.backend_notifications (
    id integer NOT NULL,
    account_id uuid NOT NULL,
    title character varying NOT NULL,
    message character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: backend_notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.backend_notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: backend_notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.backend_notifications_id_seq OWNED BY public.backend_notifications.id;


--
-- Name: corporate_authorisations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.corporate_authorisations (
    id integer NOT NULL,
    code character varying NOT NULL,
    permission public.corpauthorisation NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: corporate_authorisations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.corporate_authorisations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: corporate_authorisations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.corporate_authorisations_id_seq OWNED BY public.corporate_authorisations.id;


--
-- Name: corporate_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.corporate_users (
    id integer NOT NULL,
    ic_type public.sgimedictype NOT NULL,
    nric character varying NOT NULL,
    code character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: corporate_users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.corporate_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: corporate_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.corporate_users_id_seq OWNED BY public.corporate_users.id;


--
-- Name: patient_account_yuu_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_account_yuu_links (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    tomo_id character varying NOT NULL,
    user_identifier character varying NOT NULL,
    linked_at timestamp without time zone DEFAULT now() NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone
);


--
-- Name: patient_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_accounts (
    id uuid NOT NULL,
    sgimed_patient_id character varying,
    sgimed_auth_code character varying,
    sgimed_synced boolean DEFAULT false NOT NULL,
    ic_type public.sgimedictype NOT NULL,
    nric character varying NOT NULL,
    name character varying NOT NULL,
    gender public.sgimedgender NOT NULL,
    date_of_birth date NOT NULL,
    nationality public.sgimednationality NOT NULL,
    language public.sgimedlanguage NOT NULL,
    sgimed_diff json,
    mobile_code public.phonecountrycode NOT NULL,
    mobile_number character varying NOT NULL,
    secondary_mobile_code public.phonecountrycode,
    secondary_mobile_number character varying,
    email character varying,
    marital_status public.sgimedmaritalstatus,
    country character varying,
    postal character varying,
    address character varying,
    unit character varying,
    building character varying,
    residential_postal character varying,
    residential_address character varying,
    residential_unit character varying,
    residential_building character varying,
    allergy character varying,
    stripe_id character varying,
    default_payment_method public.paymentmethod,
    default_payment_id character varying,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: patient_appointments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_appointments (
    id uuid NOT NULL,
    sgimed_appointment_id character varying,
    corporate_code character varying,
    services json NOT NULL,
    account_id uuid,
    guests json,
    branch json NOT NULL,
    start_datetime timestamp with time zone NOT NULL,
    duration integer NOT NULL,
    survey json,
    payment_breakdown json NOT NULL,
    payment_ids character varying[] NOT NULL,
    invoice_ids character varying[] NOT NULL,
    status public.appointmentstatus NOT NULL,
    group_id character varying,
    created_by uuid,
    index integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: patient_document_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_document_types (
    id public.documenttype NOT NULL,
    sgimed_document_type_id character varying NOT NULL
);


--
-- Name: patient_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_documents (
    id uuid NOT NULL,
    sgimed_patient_id character varying NOT NULL,
    sgimed_document_id character varying NOT NULL,
    sgimed_branch_id character varying NOT NULL,
    sgimed_visit_id character varying,
    status public.documentstatus,
    name character varying NOT NULL,
    hidden boolean NOT NULL,
    document_date date NOT NULL,
    remarks character varying,
    document_type public.documenttype NOT NULL,
    notification_sent boolean NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: patient_family; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_family (
    id integer NOT NULL,
    sgimed_nok_id character varying,
    account_id uuid NOT NULL,
    nok_id uuid NOT NULL,
    relation public.sgimednokrelation NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: patient_family_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.patient_family_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: patient_family_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.patient_family_id_seq OWNED BY public.patient_family.id;


--
-- Name: patient_firebase_auths; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_firebase_auths (
    account_id uuid NOT NULL,
    firebase_uid character varying NOT NULL,
    push_token character varying,
    fcm_token character varying,
    apn_token character varying,
    device character varying,
    login_type public.firebaselogintype NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: patient_health_report_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_health_report_profiles (
    sgimed_hl7_id character varying NOT NULL,
    health_profile_id character varying NOT NULL,
    sgimed_patient_id character varying NOT NULL,
    report character varying NOT NULL
);


--
-- Name: patient_health_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patient_health_reports (
    sgimed_hl7_id character varying NOT NULL,
    sgimed_hl7_content character varying NOT NULL,
    sgimed_patient_id character varying NOT NULL,
    sgimed_report_id character varying NOT NULL,
    sgimed_report_file_date timestamp without time zone NOT NULL,
    patient_test_results character varying NOT NULL,
    report_summary character varying NOT NULL,
    disclaimer_accepted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_corporate_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_corporate_codes (
    id integer NOT NULL,
    code character varying NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    allow_user_input boolean DEFAULT false NOT NULL,
    remarks character varying,
    skip_prepayment boolean DEFAULT false NOT NULL,
    hide_invoice boolean DEFAULT false NOT NULL,
    sgimed_consultation_inventory_ids json NOT NULL,
    priority_index integer DEFAULT 100 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_corporate_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_corporate_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_corporate_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_corporate_codes_id_seq OWNED BY public.payment_corporate_codes.id;


--
-- Name: payment_dynamic_rates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_dynamic_rates (
    id integer NOT NULL,
    date character varying NOT NULL,
    timing character varying NOT NULL,
    corporate_codes json NOT NULL,
    sgimed_consultation_inventory_ids json NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_dynamic_rates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_dynamic_rates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_dynamic_rates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_dynamic_rates_id_seq OWNED BY public.payment_dynamic_rates.id;


--
-- Name: payment_invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_invoices (
    id character varying NOT NULL,
    visit_type public.visittype NOT NULL,
    account_id uuid NOT NULL,
    amount double precision NOT NULL,
    invoice_html character varying NOT NULL,
    mc_html character varying,
    items json NOT NULL,
    prescriptions json NOT NULL,
    hide_invoice boolean DEFAULT false NOT NULL,
    show_details boolean DEFAULT false NOT NULL,
    sgimed_last_edited character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_logs (
    id uuid NOT NULL,
    payment_id character varying NOT NULL,
    account_id uuid NOT NULL,
    payment_breakdown json NOT NULL,
    payment_type public.paymenttype NOT NULL,
    payment_method public.paymentmethod NOT NULL,
    payment_amount double precision NOT NULL,
    payment_provider public.paymentprovider,
    status public.paymentstatus NOT NULL,
    remarks json,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_reconciliations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_reconciliations (
    id integer NOT NULL,
    payment_id character varying NOT NULL,
    completed_at timestamp without time zone NOT NULL,
    branch character varying NOT NULL,
    patients json NOT NULL,
    sgimed_visit_id json NOT NULL,
    payment_type public.paymenttype NOT NULL,
    payment_provider public.paymentprovider NOT NULL,
    payment_method public.paymentmethod NOT NULL,
    payment_amount double precision NOT NULL,
    payment_amount_nett double precision NOT NULL,
    payment_platform_fees character varying NOT NULL
);


--
-- Name: payment_reconciliations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_reconciliations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_reconciliations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_reconciliations_id_seq OWNED BY public.payment_reconciliations.id;


--
-- Name: payment_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_tokens (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    provider public.paymentprovider NOT NULL,
    method public.paymentmethod NOT NULL,
    token character varying NOT NULL,
    details json NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_transactions (
    id integer NOT NULL,
    account_id uuid NOT NULL,
    provider public.paymentprovider NOT NULL,
    invoice_num character varying,
    type public.paymenttype NOT NULL,
    endpoint character varying NOT NULL,
    request json NOT NULL,
    response json NOT NULL,
    webhook json NOT NULL,
    status public.paymentstatus NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_transactions_id_seq OWNED BY public.payment_transactions.id;


--
-- Name: pinnacle_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_accounts (
    id uuid NOT NULL,
    supabase_uid character varying NOT NULL,
    sgimed_id character varying,
    branch_id uuid,
    name character varying NOT NULL,
    email character varying NOT NULL,
    role public.role NOT NULL,
    push_token character varying[] NOT NULL,
    enable_notifications boolean DEFAULT false NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pinnacle_blockoffs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_blockoffs (
    id integer NOT NULL,
    date date NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    allow_toggle boolean DEFAULT false NOT NULL,
    created_by character varying NOT NULL,
    remarks character varying,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pinnacle_blockoffs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pinnacle_blockoffs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pinnacle_blockoffs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pinnacle_blockoffs_id_seq OWNED BY public.pinnacle_blockoffs.id;


--
-- Name: pinnacle_branch_blockoffs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_branch_blockoffs (
    branch_id uuid NOT NULL,
    blockoff_id integer NOT NULL
);


--
-- Name: pinnacle_branch_services; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_branch_services (
    branch_id uuid NOT NULL,
    service_id integer NOT NULL
);


--
-- Name: pinnacle_branches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_branches (
    id uuid NOT NULL,
    sgimed_branch_id character varying NOT NULL,
    name character varying NOT NULL,
    address character varying,
    phone character varying,
    whatsapp character varying,
    email character varying,
    url character varying,
    image_url character varying,
    category character varying NOT NULL,
    walk_in_curr_queue_number character varying,
    sgimed_calendar_id character varying,
    branch_type public.branchtype NOT NULL,
    has_delivery_operating_hours boolean DEFAULT false NOT NULL,
    hidden boolean DEFAULT false NOT NULL,
    deleted boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pinnacle_branches_delivery_operating_hours; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_branches_delivery_operating_hours (
    id integer NOT NULL,
    branch_id uuid NOT NULL,
    day public.dayofweek NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    cutoff_time integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pinnacle_branches_delivery_operating_hours_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pinnacle_branches_delivery_operating_hours_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pinnacle_branches_delivery_operating_hours_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pinnacle_branches_delivery_operating_hours_id_seq OWNED BY public.pinnacle_branches_delivery_operating_hours.id;


--
-- Name: pinnacle_branches_operating_hours; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_branches_operating_hours (
    id integer NOT NULL,
    branch_id uuid NOT NULL,
    day public.dayofweek NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    cutoff_time integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pinnacle_branches_operating_hours_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pinnacle_branches_operating_hours_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pinnacle_branches_operating_hours_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pinnacle_branches_operating_hours_id_seq OWNED BY public.pinnacle_branches_operating_hours.id;


--
-- Name: pinnacle_content; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_content (
    id character varying NOT NULL,
    category public.contentcategory NOT NULL,
    title character varying NOT NULL,
    content character varying NOT NULL,
    sort_order integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pinnacle_payment_modes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_payment_modes (
    id public.paymentprovider NOT NULL,
    sgimed_payment_mode_id character varying NOT NULL,
    name character varying NOT NULL
);


--
-- Name: pinnacle_public_holidays; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_public_holidays (
    id integer NOT NULL,
    date date NOT NULL,
    remarks character varying,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pinnacle_public_holidays_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pinnacle_public_holidays_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pinnacle_public_holidays_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pinnacle_public_holidays_id_seq OWNED BY public.pinnacle_public_holidays.id;


--
-- Name: pinnacle_sa_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_sa_records (
    nric character varying NOT NULL,
    comp_code character varying,
    company_name character varying,
    uen character varying,
    employee_no character varying,
    employee_name character varying,
    passport character varying,
    sector character varying,
    pcp_start character varying,
    pcp_end character varying,
    checkup_mwoc character varying,
    status character varying,
    created_date_time character varying,
    termination_date character varying,
    handphone_no character varying
);


--
-- Name: pinnacle_sa_records_metadata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_sa_records_metadata (
    id integer NOT NULL,
    last_updated timestamp without time zone NOT NULL,
    total_records integer NOT NULL,
    imported_records integer,
    insert_diff character varying[] NOT NULL,
    update_diff character varying[] NOT NULL,
    delete_diff character varying[] NOT NULL
);


--
-- Name: pinnacle_sa_records_metadata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pinnacle_sa_records_metadata_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pinnacle_sa_records_metadata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pinnacle_sa_records_metadata_id_seq OWNED BY public.pinnacle_sa_records_metadata.id;


--
-- Name: pinnacle_sa_records_temp; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_sa_records_temp (
    nric character varying NOT NULL,
    comp_code character varying,
    company_name character varying,
    uen character varying,
    employee_no character varying,
    employee_name character varying,
    passport character varying,
    sector character varying,
    pcp_start character varying,
    pcp_end character varying,
    checkup_mwoc character varying,
    status character varying,
    created_date_time character varying,
    termination_date character varying,
    handphone_no character varying
);


--
-- Name: pinnacle_services; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pinnacle_services (
    id integer NOT NULL,
    label character varying NOT NULL,
    sgimed_branch_id character varying NOT NULL,
    sgimed_appointment_type_id character varying NOT NULL,
    is_for_visit boolean NOT NULL,
    is_for_appointment boolean NOT NULL,
    is_for_telemed boolean NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pinnacle_services_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pinnacle_services_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pinnacle_services_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pinnacle_services_id_seq OWNED BY public.pinnacle_services.id;


--
-- Name: sgimed_appointment_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sgimed_appointment_types (
    id character varying NOT NULL,
    name character varying NOT NULL,
    branch_id character varying NOT NULL,
    sort_key integer NOT NULL,
    is_enabled boolean NOT NULL,
    is_for_visit boolean NOT NULL,
    is_for_appointment boolean NOT NULL,
    is_block_type boolean NOT NULL,
    last_edited timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: sgimed_appointments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sgimed_appointments (
    id character varying NOT NULL,
    subject character varying NOT NULL,
    patient_id character varying,
    calendar_id character varying NOT NULL,
    branch_id character varying NOT NULL,
    is_all_day boolean NOT NULL,
    appointment_type_id character varying NOT NULL,
    is_informed boolean NOT NULL,
    is_queued boolean NOT NULL,
    is_cancelled boolean NOT NULL,
    start_datetime timestamp with time zone NOT NULL,
    end_datetime timestamp with time zone NOT NULL,
    confirm_time timestamp without time zone,
    confirm_user character varying,
    is_confirmed boolean NOT NULL,
    last_edited timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: sgimed_hl7_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sgimed_hl7_logs (
    id character varying NOT NULL,
    vendor character varying NOT NULL,
    nric character varying NOT NULL,
    branch_id character varying NOT NULL,
    patient_id character varying NOT NULL,
    report_file_id character varying NOT NULL,
    hl7_content character varying NOT NULL,
    last_edited timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: sgimed_incoming_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sgimed_incoming_reports (
    id character varying NOT NULL,
    patient_id character varying NOT NULL,
    nric character varying NOT NULL,
    vendor character varying NOT NULL,
    status character varying NOT NULL,
    branch_id character varying NOT NULL,
    visit_id character varying NOT NULL,
    file_name character varying NOT NULL,
    report_file_id character varying NOT NULL,
    file_date timestamp without time zone NOT NULL,
    info_json character varying NOT NULL,
    last_edited timestamp without time zone NOT NULL,
    health_report_generated boolean
);


--
-- Name: sgimed_inventory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sgimed_inventory (
    id character varying NOT NULL,
    code character varying NOT NULL,
    name character varying NOT NULL,
    type character varying NOT NULL,
    remark character varying,
    is_stock_tracked boolean NOT NULL,
    price double precision,
    inventory_json json,
    last_edited timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL,
    category_id character varying NOT NULL
);


--
-- Name: sgimed_measurements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sgimed_measurements (
    id character varying NOT NULL,
    branch_id character varying NOT NULL,
    patient_id character varying NOT NULL,
    type_name character varying NOT NULL,
    type_unit character varying NOT NULL,
    value character varying NOT NULL,
    measurement_date timestamp without time zone NOT NULL,
    last_edited timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: teleconsult_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teleconsult_documents (
    teleconsult_id uuid NOT NULL,
    document_id uuid NOT NULL
);


--
-- Name: teleconsult_invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teleconsult_invoices (
    teleconsult_id uuid NOT NULL,
    invoice_id character varying NOT NULL
);


--
-- Name: teleconsult_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teleconsult_payments (
    teleconsult_id uuid NOT NULL,
    payment_id uuid NOT NULL
);


--
-- Name: teleconsult_queues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teleconsult_queues (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    patient_type public.patienttype NOT NULL,
    allergy character varying,
    sgimed_visit_id character varying,
    queue_number character varying,
    queue_status character varying NOT NULL,
    address character varying NOT NULL,
    status public.teleconsultstatus NOT NULL,
    corporate_code character varying,
    payment_breakdown json NOT NULL,
    total double precision NOT NULL,
    balance double precision NOT NULL,
    collection_method public.collectionmethod,
    additional_status public.teleconsultstatus,
    doctor_id uuid,
    branch_id uuid,
    notifications_sent character varying[] NOT NULL,
    teleconsult_start_time timestamp without time zone,
    teleconsult_join_time timestamp without time zone,
    teleconsult_end_time timestamp without time zone,
    checkin_time timestamp without time zone DEFAULT now() NOT NULL,
    checkout_time timestamp without time zone,
    group_id character varying,
    index integer,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: walkin_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.walkin_documents (
    walkin_id uuid NOT NULL,
    document_id uuid NOT NULL
);


--
-- Name: walkin_invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.walkin_invoices (
    walkin_id uuid NOT NULL,
    invoice_id character varying NOT NULL
);


--
-- Name: walkin_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.walkin_payments (
    walkin_id uuid NOT NULL,
    payment_id uuid NOT NULL
);


--
-- Name: walkin_queues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.walkin_queues (
    id uuid NOT NULL,
    branch_id uuid NOT NULL,
    account_id uuid NOT NULL,
    queue_number character varying,
    sgimed_pending_queue_id character varying NOT NULL,
    sgimed_visit_id character varying,
    service character varying NOT NULL,
    queue_status character varying NOT NULL,
    checkin_time timestamp without time zone,
    checkout_time timestamp without time zone,
    status public.walkinqueuestatus NOT NULL,
    notifications_sent character varying[] NOT NULL,
    remarks character varying,
    group_id character varying,
    index integer,
    created_by uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: yuu_transaction_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.yuu_transaction_logs (
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    tomo_id character varying NOT NULL,
    sgimed_invoice_id character varying NOT NULL,
    sgimed_invoice_dict json NOT NULL,
    transaction_id character varying NOT NULL,
    yuu_payload json NOT NULL,
    success boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: appointment_counts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_counts ALTER COLUMN id SET DEFAULT nextval('public.appointment_counts_id_seq'::regclass);


--
-- Name: appointment_onsite_branches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_onsite_branches ALTER COLUMN id SET DEFAULT nextval('public.appointment_onsite_branches_id_seq'::regclass);


--
-- Name: backend_notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backend_notifications ALTER COLUMN id SET DEFAULT nextval('public.backend_notifications_id_seq'::regclass);


--
-- Name: corporate_authorisations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_authorisations ALTER COLUMN id SET DEFAULT nextval('public.corporate_authorisations_id_seq'::regclass);


--
-- Name: corporate_users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_users ALTER COLUMN id SET DEFAULT nextval('public.corporate_users_id_seq'::regclass);


--
-- Name: patient_family id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_family ALTER COLUMN id SET DEFAULT nextval('public.patient_family_id_seq'::regclass);


--
-- Name: payment_corporate_codes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_corporate_codes ALTER COLUMN id SET DEFAULT nextval('public.payment_corporate_codes_id_seq'::regclass);


--
-- Name: payment_dynamic_rates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_dynamic_rates ALTER COLUMN id SET DEFAULT nextval('public.payment_dynamic_rates_id_seq'::regclass);


--
-- Name: payment_reconciliations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_reconciliations ALTER COLUMN id SET DEFAULT nextval('public.payment_reconciliations_id_seq'::regclass);


--
-- Name: payment_transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions ALTER COLUMN id SET DEFAULT nextval('public.payment_transactions_id_seq'::regclass);


--
-- Name: pinnacle_blockoffs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_blockoffs ALTER COLUMN id SET DEFAULT nextval('public.pinnacle_blockoffs_id_seq'::regclass);


--
-- Name: pinnacle_branches_delivery_operating_hours id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branches_delivery_operating_hours ALTER COLUMN id SET DEFAULT nextval('public.pinnacle_branches_delivery_operating_hours_id_seq'::regclass);


--
-- Name: pinnacle_branches_operating_hours id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branches_operating_hours ALTER COLUMN id SET DEFAULT nextval('public.pinnacle_branches_operating_hours_id_seq'::regclass);


--
-- Name: pinnacle_public_holidays id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_public_holidays ALTER COLUMN id SET DEFAULT nextval('public.pinnacle_public_holidays_id_seq'::regclass);


--
-- Name: pinnacle_sa_records_metadata id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_sa_records_metadata ALTER COLUMN id SET DEFAULT nextval('public.pinnacle_sa_records_metadata_id_seq'::regclass);


--
-- Name: pinnacle_services id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_services ALTER COLUMN id SET DEFAULT nextval('public.pinnacle_services_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

-- ALTER TABLE ONLY public.alembic_version
--     ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: appointment_corporate_codes appointment_corporate_codes_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_corporate_codes
    ADD CONSTRAINT appointment_corporate_codes_code_key UNIQUE (code);


--
-- Name: appointment_corporate_codes appointment_corporate_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_corporate_codes
    ADD CONSTRAINT appointment_corporate_codes_pkey PRIMARY KEY (id);


--
-- Name: appointment_counts appointment_counts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_counts
    ADD CONSTRAINT appointment_counts_pkey PRIMARY KEY (id);


--
-- Name: appointment_onsite_branches appointment_onsite_branches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_onsite_branches
    ADD CONSTRAINT appointment_onsite_branches_pkey PRIMARY KEY (id);


--
-- Name: appointment_operating_hours appointment_operating_hours_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_operating_hours
    ADD CONSTRAINT appointment_operating_hours_pkey PRIMARY KEY (id);


--
-- Name: appointment_service_groups appointment_service_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_service_groups
    ADD CONSTRAINT appointment_service_groups_pkey PRIMARY KEY (id);


--
-- Name: appointment_services appointment_services_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_services
    ADD CONSTRAINT appointment_services_pkey PRIMARY KEY (id);


--
-- Name: backend_configs backend_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backend_configs
    ADD CONSTRAINT backend_configs_pkey PRIMARY KEY (key);


--
-- Name: backend_crons backend_crons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backend_crons
    ADD CONSTRAINT backend_crons_pkey PRIMARY KEY (id);


--
-- Name: backend_notifications backend_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backend_notifications
    ADD CONSTRAINT backend_notifications_pkey PRIMARY KEY (id);


--
-- Name: corporate_authorisations corporate_authorisations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_authorisations
    ADD CONSTRAINT corporate_authorisations_pkey PRIMARY KEY (id);


--
-- Name: corporate_users corporate_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.corporate_users
    ADD CONSTRAINT corporate_users_pkey PRIMARY KEY (id);


--
-- Name: patient_account_yuu_links patient_account_yuu_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_account_yuu_links
    ADD CONSTRAINT patient_account_yuu_links_pkey PRIMARY KEY (id);


--
-- Name: patient_accounts patient_accounts_nric_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_accounts
    ADD CONSTRAINT patient_accounts_nric_key UNIQUE (nric);


--
-- Name: patient_accounts patient_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_accounts
    ADD CONSTRAINT patient_accounts_pkey PRIMARY KEY (id);


--
-- Name: patient_appointments patient_appointments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_appointments
    ADD CONSTRAINT patient_appointments_pkey PRIMARY KEY (id);


--
-- Name: patient_document_types patient_document_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_document_types
    ADD CONSTRAINT patient_document_types_pkey PRIMARY KEY (id);


--
-- Name: patient_documents patient_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_documents
    ADD CONSTRAINT patient_documents_pkey PRIMARY KEY (id);


--
-- Name: patient_documents patient_documents_sgimed_document_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_documents
    ADD CONSTRAINT patient_documents_sgimed_document_id_key UNIQUE (sgimed_document_id);


--
-- Name: patient_family patient_family_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_family
    ADD CONSTRAINT patient_family_pkey PRIMARY KEY (id);


--
-- Name: patient_firebase_auths patient_firebase_auths_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_firebase_auths
    ADD CONSTRAINT patient_firebase_auths_pkey PRIMARY KEY (account_id, firebase_uid);


--
-- Name: patient_health_report_profiles patient_health_report_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_report_profiles
    ADD CONSTRAINT patient_health_report_profiles_pkey PRIMARY KEY (sgimed_hl7_id, health_profile_id);


--
-- Name: patient_health_reports patient_health_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_reports
    ADD CONSTRAINT patient_health_reports_pkey PRIMARY KEY (sgimed_hl7_id);


--
-- Name: patient_health_reports patient_health_reports_sgimed_report_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_health_reports
    ADD CONSTRAINT patient_health_reports_sgimed_report_id_key UNIQUE (sgimed_report_id);


--
-- Name: payment_corporate_codes payment_corporate_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_corporate_codes
    ADD CONSTRAINT payment_corporate_codes_pkey PRIMARY KEY (id);


--
-- Name: payment_dynamic_rates payment_dynamic_rates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_dynamic_rates
    ADD CONSTRAINT payment_dynamic_rates_pkey PRIMARY KEY (id);


--
-- Name: payment_invoices payment_invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_invoices
    ADD CONSTRAINT payment_invoices_pkey PRIMARY KEY (id);


--
-- Name: payment_logs payment_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_logs
    ADD CONSTRAINT payment_logs_pkey PRIMARY KEY (id);


--
-- Name: payment_reconciliations payment_reconciliations_payment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_reconciliations
    ADD CONSTRAINT payment_reconciliations_payment_id_key UNIQUE (payment_id);


--
-- Name: payment_reconciliations payment_reconciliations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_reconciliations
    ADD CONSTRAINT payment_reconciliations_pkey PRIMARY KEY (id);


--
-- Name: payment_tokens payment_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_tokens
    ADD CONSTRAINT payment_tokens_pkey PRIMARY KEY (id);


--
-- Name: payment_transactions payment_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_accounts pinnacle_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_accounts
    ADD CONSTRAINT pinnacle_accounts_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_blockoffs pinnacle_blockoffs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_blockoffs
    ADD CONSTRAINT pinnacle_blockoffs_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_branch_blockoffs pinnacle_branch_blockoffs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branch_blockoffs
    ADD CONSTRAINT pinnacle_branch_blockoffs_pkey PRIMARY KEY (branch_id, blockoff_id);


--
-- Name: pinnacle_branch_services pinnacle_branch_services_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branch_services
    ADD CONSTRAINT pinnacle_branch_services_pkey PRIMARY KEY (branch_id, service_id);


--
-- Name: pinnacle_branches_delivery_operating_hours pinnacle_branches_delivery_operating_hours_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branches_delivery_operating_hours
    ADD CONSTRAINT pinnacle_branches_delivery_operating_hours_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_branches_operating_hours pinnacle_branches_operating_hours_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branches_operating_hours
    ADD CONSTRAINT pinnacle_branches_operating_hours_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_branches pinnacle_branches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branches
    ADD CONSTRAINT pinnacle_branches_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_content pinnacle_content_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_content
    ADD CONSTRAINT pinnacle_content_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_payment_modes pinnacle_payment_modes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_payment_modes
    ADD CONSTRAINT pinnacle_payment_modes_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_public_holidays pinnacle_public_holidays_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_public_holidays
    ADD CONSTRAINT pinnacle_public_holidays_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_sa_records_metadata pinnacle_sa_records_metadata_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_sa_records_metadata
    ADD CONSTRAINT pinnacle_sa_records_metadata_pkey PRIMARY KEY (id);


--
-- Name: pinnacle_sa_records pinnacle_sa_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_sa_records
    ADD CONSTRAINT pinnacle_sa_records_pkey PRIMARY KEY (nric);


--
-- Name: pinnacle_sa_records_temp pinnacle_sa_records_temp_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_sa_records_temp
    ADD CONSTRAINT pinnacle_sa_records_temp_pkey PRIMARY KEY (nric);


--
-- Name: pinnacle_services pinnacle_services_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_services
    ADD CONSTRAINT pinnacle_services_pkey PRIMARY KEY (id);


--
-- Name: sgimed_appointment_types sgimed_appointment_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sgimed_appointment_types
    ADD CONSTRAINT sgimed_appointment_types_pkey PRIMARY KEY (id);


--
-- Name: sgimed_appointments sgimed_appointments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sgimed_appointments
    ADD CONSTRAINT sgimed_appointments_pkey PRIMARY KEY (id);


--
-- Name: sgimed_hl7_logs sgimed_hl7_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sgimed_hl7_logs
    ADD CONSTRAINT sgimed_hl7_logs_pkey PRIMARY KEY (id);


--
-- Name: sgimed_incoming_reports sgimed_incoming_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sgimed_incoming_reports
    ADD CONSTRAINT sgimed_incoming_reports_pkey PRIMARY KEY (id);


--
-- Name: sgimed_inventory sgimed_inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sgimed_inventory
    ADD CONSTRAINT sgimed_inventory_pkey PRIMARY KEY (id);


--
-- Name: sgimed_measurements sgimed_measurements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sgimed_measurements
    ADD CONSTRAINT sgimed_measurements_pkey PRIMARY KEY (id);


--
-- Name: teleconsult_documents teleconsult_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_documents
    ADD CONSTRAINT teleconsult_documents_pkey PRIMARY KEY (teleconsult_id, document_id);


--
-- Name: teleconsult_invoices teleconsult_invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_invoices
    ADD CONSTRAINT teleconsult_invoices_pkey PRIMARY KEY (teleconsult_id, invoice_id);


--
-- Name: teleconsult_payments teleconsult_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_payments
    ADD CONSTRAINT teleconsult_payments_pkey PRIMARY KEY (teleconsult_id, payment_id);


--
-- Name: teleconsult_queues teleconsult_queues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_queues
    ADD CONSTRAINT teleconsult_queues_pkey PRIMARY KEY (id);


--
-- Name: walkin_documents walkin_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_documents
    ADD CONSTRAINT walkin_documents_pkey PRIMARY KEY (walkin_id, document_id);


--
-- Name: walkin_invoices walkin_invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_invoices
    ADD CONSTRAINT walkin_invoices_pkey PRIMARY KEY (walkin_id, invoice_id);


--
-- Name: walkin_payments walkin_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_payments
    ADD CONSTRAINT walkin_payments_pkey PRIMARY KEY (walkin_id, payment_id);


--
-- Name: walkin_queues walkin_queues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_queues
    ADD CONSTRAINT walkin_queues_pkey PRIMARY KEY (id);


--
-- Name: yuu_transaction_logs yuu_transaction_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.yuu_transaction_logs
    ADD CONSTRAINT yuu_transaction_logs_pkey PRIMARY KEY (id);


--
-- Name: ix_appointment_counts_sgimed_branch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_appointment_counts_sgimed_branch_id ON public.appointment_counts USING btree (sgimed_branch_id);


--
-- Name: ix_appointment_counts_sgimed_calendar_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_appointment_counts_sgimed_calendar_id ON public.appointment_counts USING btree (sgimed_calendar_id);


--
-- Name: ix_appointment_counts_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_appointment_counts_time ON public.appointment_counts USING btree ("time");


--
-- Name: ix_backend_notifications_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_backend_notifications_account_id ON public.backend_notifications USING btree (account_id);


--
-- Name: ix_corporate_users_ic_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_corporate_users_ic_type ON public.corporate_users USING btree (ic_type);


--
-- Name: ix_corporate_users_nric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_corporate_users_nric ON public.corporate_users USING btree (nric);


--
-- Name: ix_patient_account_yuu_links_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_account_yuu_links_account_id ON public.patient_account_yuu_links USING btree (account_id);


--
-- Name: ix_patient_account_yuu_links_tomo_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_account_yuu_links_tomo_id ON public.patient_account_yuu_links USING btree (tomo_id);


--
-- Name: ix_patient_accounts_sgimed_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_patient_accounts_sgimed_patient_id ON public.patient_accounts USING btree (sgimed_patient_id);


--
-- Name: ix_patient_appointments_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_appointments_account_id ON public.patient_appointments USING btree (account_id);


--
-- Name: ix_patient_appointments_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_appointments_group_id ON public.patient_appointments USING btree (group_id);


--
-- Name: ix_patient_family_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_family_account_id ON public.patient_family USING btree (account_id);


--
-- Name: ix_patient_family_nok_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_family_nok_id ON public.patient_family USING btree (nok_id);


--
-- Name: ix_patient_health_report_profiles_sgimed_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_patient_health_report_profiles_sgimed_patient_id ON public.patient_health_report_profiles USING btree (sgimed_patient_id);


--
-- Name: ix_payment_corporate_codes_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_payment_corporate_codes_code ON public.payment_corporate_codes USING btree (code);


--
-- Name: ix_payment_corporate_codes_priority_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_corporate_codes_priority_index ON public.payment_corporate_codes USING btree (priority_index);


--
-- Name: ix_payment_invoices_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_invoices_account_id ON public.payment_invoices USING btree (account_id);


--
-- Name: ix_payment_logs_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_logs_account_id ON public.payment_logs USING btree (account_id);


--
-- Name: ix_payment_reconciliations_completed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_reconciliations_completed_at ON public.payment_reconciliations USING btree (completed_at);


--
-- Name: ix_payment_tokens_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_tokens_account_id ON public.payment_tokens USING btree (account_id);


--
-- Name: ix_payment_transactions_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_transactions_account_id ON public.payment_transactions USING btree (account_id);


--
-- Name: ix_pinnacle_accounts_branch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pinnacle_accounts_branch_id ON public.pinnacle_accounts USING btree (branch_id);


--
-- Name: ix_pinnacle_branches_delivery_operating_hours_branch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pinnacle_branches_delivery_operating_hours_branch_id ON public.pinnacle_branches_delivery_operating_hours USING btree (branch_id);


--
-- Name: ix_pinnacle_branches_operating_hours_branch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pinnacle_branches_operating_hours_branch_id ON public.pinnacle_branches_operating_hours USING btree (branch_id);


--
-- Name: ix_pinnacle_branches_sgimed_branch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_pinnacle_branches_sgimed_branch_id ON public.pinnacle_branches USING btree (sgimed_branch_id);


--
-- Name: ix_sgimed_appointment_types_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_appointment_types_id ON public.sgimed_appointment_types USING btree (id);


--
-- Name: ix_sgimed_hl7_logs_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_hl7_logs_patient_id ON public.sgimed_hl7_logs USING btree (patient_id);


--
-- Name: ix_sgimed_hl7_logs_report_file_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_hl7_logs_report_file_id ON public.sgimed_hl7_logs USING btree (report_file_id);


--
-- Name: ix_sgimed_incoming_reports_branch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_incoming_reports_branch_id ON public.sgimed_incoming_reports USING btree (branch_id);


--
-- Name: ix_sgimed_incoming_reports_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_incoming_reports_patient_id ON public.sgimed_incoming_reports USING btree (patient_id);


--
-- Name: ix_sgimed_incoming_reports_report_file_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_incoming_reports_report_file_id ON public.sgimed_incoming_reports USING btree (report_file_id);


--
-- Name: ix_sgimed_inventory_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_inventory_code ON public.sgimed_inventory USING btree (code);


--
-- Name: ix_sgimed_inventory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_inventory_id ON public.sgimed_inventory USING btree (id);


--
-- Name: ix_sgimed_measurements_measurement_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_measurements_measurement_date ON public.sgimed_measurements USING btree (measurement_date);


--
-- Name: ix_sgimed_measurements_patient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sgimed_measurements_patient_id ON public.sgimed_measurements USING btree (patient_id);


--
-- Name: ix_teleconsult_queues_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teleconsult_queues_account_id ON public.teleconsult_queues USING btree (account_id);


--
-- Name: ix_teleconsult_queues_branch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teleconsult_queues_branch_id ON public.teleconsult_queues USING btree (branch_id);


--
-- Name: ix_teleconsult_queues_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teleconsult_queues_created_by ON public.teleconsult_queues USING btree (created_by);


--
-- Name: ix_teleconsult_queues_doctor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teleconsult_queues_doctor_id ON public.teleconsult_queues USING btree (doctor_id);


--
-- Name: ix_walkin_queues_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_walkin_queues_account_id ON public.walkin_queues USING btree (account_id);


--
-- Name: ix_walkin_queues_branch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_walkin_queues_branch_id ON public.walkin_queues USING btree (branch_id);


--
-- Name: ix_walkin_queues_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_walkin_queues_created_by ON public.walkin_queues USING btree (created_by);


--
-- Name: ix_yuu_transaction_logs_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_yuu_transaction_logs_account_id ON public.yuu_transaction_logs USING btree (account_id);


--
-- Name: appointment_onsite_branches appointment_onsite_branches_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_onsite_branches
    ADD CONSTRAINT appointment_onsite_branches_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: appointment_onsite_branches appointment_onsite_branches_corporate_code_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_onsite_branches
    ADD CONSTRAINT appointment_onsite_branches_corporate_code_id_fkey FOREIGN KEY (corporate_code_id) REFERENCES public.appointment_corporate_codes(id);


--
-- Name: appointment_operating_hours appointment_operating_hours_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_operating_hours
    ADD CONSTRAINT appointment_operating_hours_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: appointment_service_groups appointment_service_groups_corporate_code_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_service_groups
    ADD CONSTRAINT appointment_service_groups_corporate_code_id_fkey FOREIGN KEY (corporate_code_id) REFERENCES public.appointment_corporate_codes(id);


--
-- Name: appointment_services appointment_services_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.appointment_services
    ADD CONSTRAINT appointment_services_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.appointment_service_groups(id);


--
-- Name: backend_notifications backend_notifications_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backend_notifications
    ADD CONSTRAINT backend_notifications_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: patient_account_yuu_links patient_account_yuu_links_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_account_yuu_links
    ADD CONSTRAINT patient_account_yuu_links_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: patient_appointments patient_appointments_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_appointments
    ADD CONSTRAINT patient_appointments_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: patient_appointments patient_appointments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_appointments
    ADD CONSTRAINT patient_appointments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.patient_accounts(id);


--
-- Name: patient_family patient_family_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_family
    ADD CONSTRAINT patient_family_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: patient_family patient_family_nok_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_family
    ADD CONSTRAINT patient_family_nok_id_fkey FOREIGN KEY (nok_id) REFERENCES public.patient_accounts(id);


--
-- Name: patient_firebase_auths patient_firebase_auths_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patient_firebase_auths
    ADD CONSTRAINT patient_firebase_auths_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: payment_invoices payment_invoices_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_invoices
    ADD CONSTRAINT payment_invoices_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: payment_logs payment_logs_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_logs
    ADD CONSTRAINT payment_logs_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: payment_tokens payment_tokens_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_tokens
    ADD CONSTRAINT payment_tokens_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: payment_transactions payment_transactions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_transactions
    ADD CONSTRAINT payment_transactions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: pinnacle_accounts pinnacle_accounts_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_accounts
    ADD CONSTRAINT pinnacle_accounts_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: pinnacle_branch_blockoffs pinnacle_branch_blockoffs_blockoff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branch_blockoffs
    ADD CONSTRAINT pinnacle_branch_blockoffs_blockoff_id_fkey FOREIGN KEY (blockoff_id) REFERENCES public.pinnacle_blockoffs(id) ON DELETE CASCADE;


--
-- Name: pinnacle_branch_blockoffs pinnacle_branch_blockoffs_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branch_blockoffs
    ADD CONSTRAINT pinnacle_branch_blockoffs_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: pinnacle_branch_services pinnacle_branch_services_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branch_services
    ADD CONSTRAINT pinnacle_branch_services_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: pinnacle_branch_services pinnacle_branch_services_service_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branch_services
    ADD CONSTRAINT pinnacle_branch_services_service_id_fkey FOREIGN KEY (service_id) REFERENCES public.pinnacle_services(id) ON DELETE CASCADE;


--
-- Name: pinnacle_branches_delivery_operating_hours pinnacle_branches_delivery_operating_hours_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branches_delivery_operating_hours
    ADD CONSTRAINT pinnacle_branches_delivery_operating_hours_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: pinnacle_branches_operating_hours pinnacle_branches_operating_hours_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pinnacle_branches_operating_hours
    ADD CONSTRAINT pinnacle_branches_operating_hours_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: teleconsult_documents teleconsult_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_documents
    ADD CONSTRAINT teleconsult_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.patient_documents(id);


--
-- Name: teleconsult_documents teleconsult_documents_teleconsult_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_documents
    ADD CONSTRAINT teleconsult_documents_teleconsult_id_fkey FOREIGN KEY (teleconsult_id) REFERENCES public.teleconsult_queues(id);


--
-- Name: teleconsult_invoices teleconsult_invoices_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_invoices
    ADD CONSTRAINT teleconsult_invoices_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.payment_invoices(id);


--
-- Name: teleconsult_invoices teleconsult_invoices_teleconsult_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_invoices
    ADD CONSTRAINT teleconsult_invoices_teleconsult_id_fkey FOREIGN KEY (teleconsult_id) REFERENCES public.teleconsult_queues(id);


--
-- Name: teleconsult_payments teleconsult_payments_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_payments
    ADD CONSTRAINT teleconsult_payments_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payment_logs(id);


--
-- Name: teleconsult_payments teleconsult_payments_teleconsult_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_payments
    ADD CONSTRAINT teleconsult_payments_teleconsult_id_fkey FOREIGN KEY (teleconsult_id) REFERENCES public.teleconsult_queues(id);


--
-- Name: teleconsult_queues teleconsult_queues_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_queues
    ADD CONSTRAINT teleconsult_queues_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: teleconsult_queues teleconsult_queues_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_queues
    ADD CONSTRAINT teleconsult_queues_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: teleconsult_queues teleconsult_queues_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_queues
    ADD CONSTRAINT teleconsult_queues_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.patient_accounts(id);


--
-- Name: teleconsult_queues teleconsult_queues_doctor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teleconsult_queues
    ADD CONSTRAINT teleconsult_queues_doctor_id_fkey FOREIGN KEY (doctor_id) REFERENCES public.pinnacle_accounts(id);


--
-- Name: walkin_documents walkin_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_documents
    ADD CONSTRAINT walkin_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.patient_documents(id);


--
-- Name: walkin_documents walkin_documents_walkin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_documents
    ADD CONSTRAINT walkin_documents_walkin_id_fkey FOREIGN KEY (walkin_id) REFERENCES public.walkin_queues(id);


--
-- Name: walkin_invoices walkin_invoices_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_invoices
    ADD CONSTRAINT walkin_invoices_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.payment_invoices(id);


--
-- Name: walkin_invoices walkin_invoices_walkin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_invoices
    ADD CONSTRAINT walkin_invoices_walkin_id_fkey FOREIGN KEY (walkin_id) REFERENCES public.walkin_queues(id);


--
-- Name: walkin_payments walkin_payments_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_payments
    ADD CONSTRAINT walkin_payments_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payment_logs(id);


--
-- Name: walkin_payments walkin_payments_walkin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_payments
    ADD CONSTRAINT walkin_payments_walkin_id_fkey FOREIGN KEY (walkin_id) REFERENCES public.walkin_queues(id);


--
-- Name: walkin_queues walkin_queues_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_queues
    ADD CONSTRAINT walkin_queues_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);


--
-- Name: walkin_queues walkin_queues_branch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_queues
    ADD CONSTRAINT walkin_queues_branch_id_fkey FOREIGN KEY (branch_id) REFERENCES public.pinnacle_branches(id);


--
-- Name: walkin_queues walkin_queues_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.walkin_queues
    ADD CONSTRAINT walkin_queues_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.patient_accounts(id);


--
-- Name: yuu_transaction_logs yuu_transaction_logs_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.yuu_transaction_logs
    ADD CONSTRAINT yuu_transaction_logs_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.patient_accounts(id);
