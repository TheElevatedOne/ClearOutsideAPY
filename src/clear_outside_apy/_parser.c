#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

#define MAX_DAYS 8
#define MAX_HOURS 32
#define NOINT ((int)0x80000000)
#define MILES_TO_KM 1.609344

static PyObject *ParseError = NULL;

enum RowKind {
    ROW_UNKNOWN = 0,
    ROW_TOTAL_CLOUDS,
    ROW_LOW_CLOUDS,
    ROW_MID_CLOUDS,
    ROW_HIGH_CLOUDS,
    ROW_ISS,
    ROW_VIS,
    ROW_FOG,
    ROW_PREC_TYPE,
    ROW_PREC_PROB,
    ROW_PREC_AMT,
    ROW_WIND,
    ROW_FROST,
    ROW_TEMP,
    ROW_FEELS,
    ROW_DEW,
    ROW_HUMID,
    ROW_PRESS,
    ROW_OZONE,
    ROW_METNO_TOTAL,
    ROW_METNO_LOW,
    ROW_METNO_MID,
    ROW_METNO_HIGH,
    ROW_T7_CLOUD,
    ROW_T7_SEEING,
    ROW_T7_LIFTED,
    ROW_T7_TRANS
};

typedef struct {
    char hour[8];
    char conditions[12];
    int total_clouds, low_clouds, mid_clouds, high_clouds;
    double visibility;
    int has_vis;
    int fog;
    char prec_type[64];
    int prec_prob;
    double prec_amt;
    int has_prec_amt;
    double wind_speed;
    int has_wind;
    char wind_dir[40];
    int wind_deg;
    int has_wind_deg;
    int frost; /* -1 missing, 0 none, 1 frost */
    int temp, feels, dew;
    int humidity, pressure, ozone;
    int has_iss;
    char iss_raw[768];
    int metno_total, metno_low, metno_mid, metno_high;
    int t7_cloud, t7_seeing, t7_lifted, t7_trans;
    int has_extra;
} Hour;

typedef struct {
    char weekday[32];
    char day_short[8];
    char moon_phase[64];
    int moon_pct;
    char moon_rise[16];
    char moon_set[16];
    int has_moon_rise, has_moon_set;
    char moon_rise_date[16];
    char moon_set_date[16];
    char mer_time[16];
    char mer_date[16];
    double mer_alt;
    int has_mer_alt;
    double mer_dist_miles;
    int has_mer_dist;
    char sun_rise[16];
    char sun_set[16];
    char sun_transit[16];
    char civil_from[16], civil_to[16];
    char naut_from[16], naut_to[16];
    char astro_from[16], astro_to[16];
    Hour hours[MAX_HOURS];
    int nhours;
    int has_extra;
} Day;

static const char *find_n(const char *p, const char *end, const char *needle)
{
    size_t n = strlen(needle);
    const char *lim;
    if (n == 0) {
        return p;
    }
    if (p >= end || (size_t)(end - p) < n) {
        return NULL;
    }
    lim = end - (Py_ssize_t)n;
    for (; p <= lim; p++) {
        if (p[0] == needle[0] && memcmp(p, needle, n) == 0) {
            return p;
        }
    }
    return NULL;
}

static const char *tag_close(const char *p, const char *end)
{
    int quote = 0;
    for (; p < end; p++) {
        if (quote) {
            if (*p == quote) {
                quote = 0;
            }
        } else if (*p == '"' || *p == '\'') {
            quote = (unsigned char)*p;
        } else if (*p == '>') {
            return p;
        }
    }
    return NULL;
}

static int is_ws(unsigned char c)
{
    return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

static unsigned long parse_ulong(const char *s, const char **end, int base);

static void trim_inplace(char *s)
{
    char *start = s;
    char *end;
    size_t len;
    while (*start && is_ws((unsigned char)*start)) {
        start++;
    }
    if (start != s) {
        memmove(s, start, strlen(start) + 1);
    }
    len = strlen(s);
    end = s + len;
    while (end > s && is_ws((unsigned char)end[-1])) {
        end--;
    }
    *end = '\0';
}

static void collapse_ws(char *s)
{
    char *r = s, *w = s;
    int prev_sp = 1;
    for (; *r; r++) {
        if (is_ws((unsigned char)*r)) {
            if (!prev_sp) {
                *w++ = ' ';
                prev_sp = 1;
            }
        } else {
            *w++ = *r;
            prev_sp = 0;
        }
    }
    if (w > s && w[-1] == ' ') {
        w--;
    }
    *w = '\0';
}

static Py_ssize_t html_text(const char *s, const char *e, char *out, Py_ssize_t outsz)
{
    Py_ssize_t n = 0;
    int in_tag = 0;
    int quote = 0;

    if (outsz < 2) {
        return 0;
    }
    while (s < e && n + 5 < outsz) {
        if (in_tag) {
            if (quote) {
                if (*s == quote) {
                    quote = 0;
                }
            } else if (*s == '"' || *s == '\'') {
                quote = (unsigned char)*s;
            } else if (*s == '>') {
                in_tag = 0;
            }
            s++;
            continue;
        }
        if (*s == '<') {
            in_tag = 1;
            s++;
            continue;
        }
        if (*s == '&') {
            if (e - s >= 6 && memcmp(s, "&nbsp;", 6) == 0) {
                out[n++] = ' ';
                s += 6;
                continue;
            }
            if (e - s >= 5 && memcmp(s, "&deg;", 5) == 0) {
                out[n++] = (char)0xC2;
                out[n++] = (char)0xB0;
                s += 5;
                continue;
            }
            if (e - s >= 5 && memcmp(s, "&amp;", 5) == 0) {
                out[n++] = '&';
                s += 5;
                continue;
            }
            if (e - s >= 4 && memcmp(s, "&lt;", 4) == 0) {
                out[n++] = '<';
                s += 4;
                continue;
            }
            if (e - s >= 4 && memcmp(s, "&gt;", 4) == 0) {
                out[n++] = '>';
                s += 4;
                continue;
            }
            if (e - s >= 6 && memcmp(s, "&quot;", 6) == 0) {
                out[n++] = '"';
                s += 6;
                continue;
            }
            if (e - s >= 3 && s[1] == '#') {
                const char *num = s + 2;
                int hex = 0;
                unsigned long cp;
                const char *endptr;
                if (*num == 'x' || *num == 'X') {
                    hex = 1;
                    num++;
                }
                cp = parse_ulong(num, &endptr, hex ? 16 : 10);
                if (endptr > num && *endptr == ';') {
                    if (cp < 0x80) {
                        out[n++] = (char)cp;
                    } else if (cp < 0x800) {
                        out[n++] = (char)(0xC0 | (cp >> 6));
                        out[n++] = (char)(0x80 | (cp & 0x3F));
                    } else {
                        out[n++] = (char)(0xE0 | (cp >> 12));
                        out[n++] = (char)(0x80 | ((cp >> 6) & 0x3F));
                        out[n++] = (char)(0x80 | (cp & 0x3F));
                    }
                    s = endptr + 1;
                    continue;
                }
            }
        }
        out[n++] = *s++;
    }
    out[n] = '\0';
    collapse_ws(out);
    return (Py_ssize_t)strlen(out);
}

static int get_attr(const char *tag, const char *tag_end, const char *name,
                    const char **vs, const char **ve)
{
    size_t nlen = strlen(name);
    const char *p = tag;
    while (p + nlen + 3 < tag_end) {
        if ((p == tag || is_ws((unsigned char)p[-1])) &&
            memcmp(p, name, nlen) == 0 && p[nlen] == '=') {
            const char *q = p + nlen + 1;
            char quote;
            if (q >= tag_end) {
                return 0;
            }
            quote = *q;
            if (quote != '"' && quote != '\'') {
                return 0;
            }
            q++;
            *vs = q;
            while (q < tag_end && *q != quote) {
                q++;
            }
            *ve = q;
            return 1;
        }
        p++;
    }
    return 0;
}

static int copy_attr(const char *tag, const char *tag_end, const char *name,
                     char *out, size_t outsz)
{
    const char *vs, *ve;
    Py_ssize_t n;
    if (!get_attr(tag, tag_end, name, &vs, &ve)) {
        out[0] = '\0';
        return 0;
    }
    n = html_text(vs, ve, out, (Py_ssize_t)outsz);
    return n > 0;
}

static int copy_attr_raw(const char *tag, const char *tag_end, const char *name,
                         char *out, size_t outsz)
{
    const char *vs, *ve;
    size_t n;
    if (!get_attr(tag, tag_end, name, &vs, &ve)) {
        out[0] = '\0';
        return 0;
    }
    n = (size_t)(ve - vs);
    if (n >= outsz) {
        n = outsz - 1;
    }
    memcpy(out, vs, n);
    out[n] = '\0';
    return n > 0;
}

static double round2(double x)
{
    if (x >= 0.0) {
        return (double)((long long)(x * 100.0 + 0.5)) / 100.0;
    }
    return (double)((long long)(x * 100.0 - 0.5)) / 100.0;
}

/* Hand-rolled so we do not pick up glibc 2.38's __isoc23_strtol. */
static unsigned long parse_ulong(const char *s, const char **end, int base)
{
    unsigned long v = 0;
    int digit;
    while (*s) {
        if (*s >= '0' && *s <= '9') {
            digit = *s - '0';
        } else if (base == 16 && *s >= 'a' && *s <= 'f') {
            digit = *s - 'a' + 10;
        } else if (base == 16 && *s >= 'A' && *s <= 'F') {
            digit = *s - 'A' + 10;
        } else {
            break;
        }
        if (digit >= base) {
            break;
        }
        v = v * (unsigned long)base + (unsigned long)digit;
        s++;
    }
    *end = s;
    return v;
}

static int parse_int_text(const char *s, int *out)
{
    int sign = 1;
    const char *end;
    unsigned long v;
    while (*s && is_ws((unsigned char)*s)) {
        s++;
    }
    if (!*s || (s[0] == '-' && s[1] == '\0')) {
        return 0;
    }
    if (*s == '-') {
        sign = -1;
        s++;
    } else if (*s == '+') {
        s++;
    }
    if (*s < '0' || *s > '9') {
        return 0;
    }
    v = parse_ulong(s, &end, 10);
    if (end == s) {
        return 0;
    }
    *out = (int)v * sign;
    return 1;
}

static int parse_double_text(const char *s, double *out)
{
    char *end;
    double v;
    while (*s && is_ws((unsigned char)*s)) {
        s++;
    }
    if (!*s || (s[0] == '-' && s[1] == '\0')) {
        return 0;
    }
    v = strtod(s, &end);
    if (end == s) {
        return 0;
    }
    *out = v;
    return 1;
}

static int looks_missing_time(const char *s)
{
    if (!s || !s[0]) {
        return 1;
    }
    if (strcmp(s, "No") == 0 || strcmp(s, "-") == 0) {
        return 1;
    }
    if (strncmp(s, "No Rise", 7) == 0 || strncmp(s, "No Set", 6) == 0) {
        return 1;
    }
    return 0;
}

/* HH:MM or HH:MM:SS — reject labels such as "Set:" after an empty Rise field. */
static int is_clock(const char *s)
{
    int digits = 0, colons = 0;
    if (!s || !s[0]) {
        return 0;
    }
    for (; *s; s++) {
        if (*s >= '0' && *s <= '9') {
            digits++;
        } else if (*s == ':' && digits > 0) {
            colons++;
            digits = 0;
        } else {
            return 0;
        }
    }
    return colons >= 1 && digits > 0;
}

static void copy_tok(char *dst, size_t dstsz, const char *src)
{
    size_t n = strlen(src);
    if (n >= dstsz) {
        n = dstsz - 1;
    }
    memcpy(dst, src, n);
    dst[n] = '\0';
}

static const char *after_label(const char *s, const char *label)
{
    const char *h = strstr(s, label);
    if (!h) {
        return NULL;
    }
    h += strlen(label);
    while (*h && is_ws((unsigned char)*h)) {
        h++;
    }
    return h;
}

static int read_word(const char **pp, char *out, size_t outsz)
{
    const char *p = *pp;
    size_t n = 0;
    while (*p && is_ws((unsigned char)*p)) {
        p++;
    }
    if (!*p) {
        out[0] = '\0';
        return 0;
    }
    while (*p && !is_ws((unsigned char)*p) && n + 1 < outsz) {
        out[n++] = *p++;
    }
    out[n] = '\0';
    *pp = p;
    return n > 0;
}

static void kebab_lower(const char *src, char *dst, size_t dstsz)
{
    size_t n = 0;
    for (; *src && n + 1 < dstsz; src++) {
        unsigned char c = (unsigned char)*src;
        if (c == ' ' || c == '_' || c == '/') {
            if (n > 0 && dst[n - 1] != '-') {
                dst[n++] = '-';
            }
        } else {
            dst[n++] = (char)tolower(c);
        }
    }
    dst[n] = '\0';
}

static void hour_init(Hour *h)
{
    memset(h, 0, sizeof(*h));
    h->total_clouds = NOINT;
    h->low_clouds = NOINT;
    h->mid_clouds = NOINT;
    h->high_clouds = NOINT;
    h->fog = NOINT;
    h->prec_prob = NOINT;
    h->temp = NOINT;
    h->feels = NOINT;
    h->dew = NOINT;
    h->humidity = NOINT;
    h->pressure = NOINT;
    h->ozone = NOINT;
    h->frost = -1;
    h->metno_total = NOINT;
    h->metno_low = NOINT;
    h->metno_mid = NOINT;
    h->metno_high = NOINT;
    h->t7_cloud = NOINT;
    h->t7_seeing = NOINT;
    h->t7_lifted = NOINT;
    h->t7_trans = NOINT;
}

static void day_init(Day *d)
{
    int i;
    memset(d, 0, sizeof(*d));
    d->moon_pct = NOINT;
    for (i = 0; i < MAX_HOURS; i++) {
        hour_init(&d->hours[i]);
    }
}

static int classify_label(const char *label)
{
    if (strstr(label, "Met.no Forecast % Total")) {
        return ROW_METNO_TOTAL;
    }
    if (strstr(label, "Met.no Forecast % Low")) {
        return ROW_METNO_LOW;
    }
    if (strstr(label, "Met.no Forecast % Medium")) {
        return ROW_METNO_MID;
    }
    if (strstr(label, "Met.no Forecast % High")) {
        return ROW_METNO_HIGH;
    }
    if (strstr(label, "7Timer Cloud Cover")) {
        return ROW_T7_CLOUD;
    }
    if (strstr(label, "7Timer Seeing")) {
        return ROW_T7_SEEING;
    }
    if (strstr(label, "7Timer Lifted")) {
        return ROW_T7_LIFTED;
    }
    if (strstr(label, "7Timer Transparency")) {
        return ROW_T7_TRANS;
    }
    if (strstr(label, "Total Clouds")) {
        return ROW_TOTAL_CLOUDS;
    }
    if (strstr(label, "Low Clouds")) {
        return ROW_LOW_CLOUDS;
    }
    if (strstr(label, "Medium Clouds")) {
        return ROW_MID_CLOUDS;
    }
    if (strstr(label, "High Clouds")) {
        return ROW_HIGH_CLOUDS;
    }
    if (strstr(label, "ISS Passover")) {
        return ROW_ISS;
    }
    if (strstr(label, "Visibility")) {
        return ROW_VIS;
    }
    if (strstr(label, "Fog")) {
        return ROW_FOG;
    }
    if (strstr(label, "Precipitation Type")) {
        return ROW_PREC_TYPE;
    }
    if (strstr(label, "Precipitation Probability")) {
        return ROW_PREC_PROB;
    }
    if (strstr(label, "Precipitation Amount")) {
        return ROW_PREC_AMT;
    }
    if (strstr(label, "Wind Speed")) {
        return ROW_WIND;
    }
    if (strstr(label, "Chance of Frost")) {
        return ROW_FROST;
    }
    if (strstr(label, "Feels Like")) {
        return ROW_FEELS;
    }
    if (strstr(label, "Dew Point")) {
        return ROW_DEW;
    }
    if (strstr(label, "Temperature")) {
        return ROW_TEMP;
    }
    if (strstr(label, "Relative Humidity")) {
        return ROW_HUMID;
    }
    if (strstr(label, "Pressure")) {
        return ROW_PRESS;
    }
    if (strstr(label, "Ozone")) {
        return ROW_OZONE;
    }
    return ROW_UNKNOWN;
}

static int is_extra_row(int kind)
{
    return kind >= ROW_METNO_TOTAL && kind <= ROW_T7_TRANS;
}

static void set_int_field(int *slot, const char *text)
{
    int v;
    if (parse_int_text(text, &v)) {
        *slot = v;
    }
}

static void parse_iss_blob(const char *raw, Hour *hour)
{
    char decoded[768];
    const char *p;
    char mag[32];
    html_text(raw, raw + strlen(raw), decoded, sizeof(decoded));
    copy_tok(hour->iss_raw, sizeof(hour->iss_raw), decoded);
    hour->has_iss = decoded[0] != '\0';
    (void)p;
    (void)mag;
}

static void apply_wind(Hour *hour, const char *cls, const char *title, const char *text)
{
    const char *p;
    char dir[40];
    int deg;
    double spd;
    p = cls;
    if (strncmp(p, "fc_wind", 7) == 0) {
        p += 7;
        while (*p && is_ws((unsigned char)*p)) {
            p++;
        }
        {
            size_t n = 0;
            while (*p && !is_ws((unsigned char)*p) && n + 1 < sizeof(dir)) {
                dir[n++] = *p++;
            }
            dir[n] = '\0';
            if (dir[0]) {
                copy_tok(hour->wind_dir, sizeof(hour->wind_dir), dir);
            }
        }
    }
    if (parse_double_text(text, &spd)) {
        hour->wind_speed = spd;
        hour->has_wind = 1;
    }
    if (title[0]) {
        const char *lp = strchr(title, '(');
        if (lp && parse_int_text(lp + 1, &deg)) {
            hour->wind_deg = deg;
            hour->has_wind_deg = 1;
        }
    }
}

static void apply_row(int kind, Hour *hour, const char *cls, const char *title,
                      const char *text, const char *data_content)
{
    switch (kind) {
    case ROW_TOTAL_CLOUDS:
        set_int_field(&hour->total_clouds, text);
        break;
    case ROW_LOW_CLOUDS:
        set_int_field(&hour->low_clouds, text);
        break;
    case ROW_MID_CLOUDS:
        set_int_field(&hour->mid_clouds, text);
        break;
    case ROW_HIGH_CLOUDS:
        set_int_field(&hour->high_clouds, text);
        break;
    case ROW_ISS:
        if (strstr(cls, "fc_iss") && data_content[0]) {
            parse_iss_blob(data_content, hour);
        }
        break;
    case ROW_VIS:
        if (parse_double_text(text, &hour->visibility)) {
            hour->has_vis = 1;
        }
        break;
    case ROW_FOG:
        set_int_field(&hour->fog, text);
        break;
    case ROW_PREC_TYPE: {
        const char *src = title[0] ? title : text;
        if (!src[0] || (tolower((unsigned char)src[0]) == 'n' &&
                        tolower((unsigned char)src[1]) == 'o' &&
                        tolower((unsigned char)src[2]) == 'n' &&
                        tolower((unsigned char)src[3]) == 'e' &&
                        src[4] == '\0')) {
            copy_tok(hour->prec_type, sizeof(hour->prec_type), "none");
        } else {
            kebab_lower(src, hour->prec_type, sizeof(hour->prec_type));
        }
        break;
    }
    case ROW_PREC_PROB:
        set_int_field(&hour->prec_prob, text);
        break;
    case ROW_PREC_AMT:
        if (parse_double_text(text, &hour->prec_amt)) {
            hour->has_prec_amt = 1;
        }
        break;
    case ROW_WIND:
        apply_wind(hour, cls, title, text);
        break;
    case ROW_FROST:
        if (strstr(title, "No Frost") || strstr(cls, "fc_none")) {
            hour->frost = 0;
        } else if (strstr(title, "Frost") || strstr(cls, "snowflake")) {
            hour->frost = 1;
        } else {
            hour->frost = 0;
        }
        break;
    case ROW_TEMP:
        set_int_field(&hour->temp, text);
        break;
    case ROW_FEELS:
        set_int_field(&hour->feels, text);
        break;
    case ROW_DEW:
        set_int_field(&hour->dew, text);
        break;
    case ROW_HUMID:
        set_int_field(&hour->humidity, text);
        break;
    case ROW_PRESS:
        set_int_field(&hour->pressure, text);
        break;
    case ROW_OZONE:
        set_int_field(&hour->ozone, text);
        break;
    case ROW_METNO_TOTAL:
        set_int_field(&hour->metno_total, text);
        hour->has_extra = 1;
        break;
    case ROW_METNO_LOW:
        set_int_field(&hour->metno_low, text);
        hour->has_extra = 1;
        break;
    case ROW_METNO_MID:
        set_int_field(&hour->metno_mid, text);
        hour->has_extra = 1;
        break;
    case ROW_METNO_HIGH:
        set_int_field(&hour->metno_high, text);
        hour->has_extra = 1;
        break;
    case ROW_T7_CLOUD:
        set_int_field(&hour->t7_cloud, text);
        hour->has_extra = 1;
        break;
    case ROW_T7_SEEING:
        set_int_field(&hour->t7_seeing, text);
        hour->has_extra = 1;
        break;
    case ROW_T7_LIFTED:
        set_int_field(&hour->t7_lifted, text);
        hour->has_extra = 1;
        break;
    case ROW_T7_TRANS:
        set_int_field(&hour->t7_trans, text);
        hour->has_extra = 1;
        break;
    default:
        break;
    }
}

static int parse_lis(const char *ul, const char *block_end, int kind, Day *day)
{
    const char *ul_end;
    const char *p;
    int count = 0;
    ul_end = find_n(ul, block_end, "</ul>");
    if (!ul_end) {
        return 0;
    }
    p = ul;
    while (count < MAX_HOURS) {
        const char *li = find_n(p, ul_end, "<li");
        const char *gt, *li_end;
        char cls[160], title[256], text[128], data[1024];
        Hour *hour;
        if (!li) {
            break;
        }
        gt = tag_close(li, ul_end);
        if (!gt) {
            break;
        }
        li_end = find_n(gt, ul_end, "</li>");
        if (!li_end) {
            break;
        }
        cls[0] = title[0] = text[0] = data[0] = '\0';
        copy_attr(li, gt, "class", cls, sizeof(cls));
        copy_attr(li, gt, "title", title, sizeof(title));
        copy_attr_raw(li, gt, "data-content", data, sizeof(data));
        html_text(gt + 1, li_end, text, sizeof(text));
        if (count >= day->nhours) {
            /* hour ratings should already have set nhours; extra cells ignored */
            if (day->nhours == 0) {
                hour_init(&day->hours[count]);
                day->nhours = count + 1;
            } else {
                p = li_end + 5;
                continue;
            }
        }
        hour = &day->hours[count];
        apply_row(kind, hour, cls, title, text, data);
        count++;
        p = li_end + 5;
    }
    return count;
}

static void parse_hour_ratings(const char *day_s, const char *day_e, Day *day)
{
    const char *block = find_n(day_s, day_e, "class=\"fc_hours fc_hour_ratings\"");
    const char *ul, *ul_end, *p;
    if (!block) {
        return;
    }
    ul = find_n(block, day_e, "<ul");
    if (!ul) {
        return;
    }
    ul_end = find_n(ul, day_e, "</ul>");
    if (!ul_end) {
        return;
    }
    p = ul;
    day->nhours = 0;
    while (day->nhours < MAX_HOURS) {
        const char *li = find_n(p, ul_end, "<li");
        const char *gt, *li_end;
        char cls[80], text[64], hour[8], cond[12];
        const char *tp;
        if (!li) {
            break;
        }
        gt = tag_close(li, ul_end);
        if (!gt) {
            break;
        }
        li_end = find_n(gt, ul_end, "</li>");
        if (!li_end) {
            break;
        }
        copy_attr(li, gt, "class", cls, sizeof(cls));
        html_text(gt + 1, li_end, text, sizeof(text));
        cond[0] = '\0';
        if (strstr(cls, "fc_good")) {
            copy_tok(cond, sizeof(cond), "good");
        } else if (strstr(cls, "fc_ok")) {
            copy_tok(cond, sizeof(cond), "ok");
        } else if (strstr(cls, "fc_bad")) {
            copy_tok(cond, sizeof(cond), "bad");
        }
        tp = text;
        hour[0] = '\0';
        read_word(&tp, hour, sizeof(hour));
        copy_tok(day->hours[day->nhours].hour, sizeof(day->hours[0].hour), hour);
        copy_tok(day->hours[day->nhours].conditions,
                 sizeof(day->hours[0].conditions), cond);
        day->nhours++;
        p = li_end + 5;
    }
}

static int parse_time_token(const char **pp, char *out, size_t outsz)
{
    const char *save = *pp;
    char tok[32];
    if (!read_word(pp, tok, sizeof(tok))) {
        return 0;
    }
    if (looks_missing_time(tok)) {
        /* consume a following Rise/Set word if present */
        const char *save2 = *pp;
        char nxt[16];
        if (read_word(pp, nxt, sizeof(nxt)) &&
            (strcmp(nxt, "Rise") == 0 || strcmp(nxt, "Set") == 0)) {
            /* "No Rise" / "No Set" */
        } else {
            *pp = save2;
        }
        out[0] = '\0';
        return 0;
    }
    if (!is_clock(tok)) {
        *pp = save;
        out[0] = '\0';
        return 0;
    }
    copy_tok(out, outsz, tok);
    return 1;
}

static void parse_maybe_date(const char **pp, char *out, size_t outsz)
{
    const char *save = *pp;
    char tok[32];
    if (!read_word(pp, tok, sizeof(tok))) {
        return;
    }
    if (strchr(tok, '/')) {
        copy_tok(out, outsz, tok);
    } else {
        *pp = save;
    }
}

static void parse_moon(const char *day_s, const char *day_e, Day *day)
{
    const char *moon = find_n(day_s, day_e, "class=\"fc_moon\"");
    const char *tag, *gt, *div_end;
    char data[1024], decoded[1024];
    const char *p;
    if (!moon) {
        return;
    }
    tag = moon;
    while (tag > day_s && *tag != '<') {
        tag--;
    }
    gt = tag_close(tag, day_e);
    if (!gt) {
        return;
    }
    div_end = find_n(gt, day_e, "class=\"fc_hours fc_hour_ratings\"");
    if (!div_end) {
        div_end = day_e;
    }
    copy_attr_raw(tag, gt, "data-content", data, sizeof(data));
    if (data[0]) {
        const char *q;
        html_text(data, data + strlen(data), decoded, sizeof(decoded));
        q = after_label(decoded, "Time:");
        if (q) {
            parse_time_token(&q, day->mer_time, sizeof(day->mer_time));
            parse_maybe_date(&q, day->mer_date, sizeof(day->mer_date));
        }
        q = after_label(decoded, "Altitude:");
        if (q) {
            double alt;
            if (parse_double_text(q, &alt)) {
                day->mer_alt = alt;
                day->has_mer_alt = 1;
            }
        }
        q = after_label(decoded, "Distance:");
        if (q) {
            char num[32];
            char stripped[32];
            size_t i, j = 0;
            read_word(&q, num, sizeof(num));
            for (i = 0; num[i] && j + 1 < sizeof(stripped); i++) {
                if (num[i] != ',') {
                    stripped[j++] = num[i];
                }
            }
            stripped[j] = '\0';
            if (parse_double_text(stripped, &day->mer_dist_miles)) {
                day->has_mer_dist = 1;
            }
        }
        q = after_label(decoded, "Rise:");
        if (q) {
            if (parse_time_token(&q, day->moon_rise, sizeof(day->moon_rise))) {
                day->has_moon_rise = 1;
                parse_maybe_date(&q, day->moon_rise_date, sizeof(day->moon_rise_date));
            }
        }
        q = after_label(decoded, "Set:");
        if (q) {
            if (parse_time_token(&q, day->moon_set, sizeof(day->moon_set))) {
                day->has_moon_set = 1;
                parse_maybe_date(&q, day->moon_set_date, sizeof(day->moon_set_date));
            }
        }
    }
    /* visible phase / percentage / rise-set labels */
    p = find_n(gt, div_end, "class=\"fc_moon_phase\"");
    if (p) {
        const char *a = tag_close(p, div_end);
        const char *b = a ? find_n(a, div_end, "</span>") : NULL;
        if (a && b) {
            html_text(a + 1, b, day->moon_phase, sizeof(day->moon_phase));
        }
    }
    p = find_n(gt, div_end, "class=\"fc_moon_percentage\"");
    if (p) {
        const char *a = tag_close(p, div_end);
        const char *b = a ? find_n(a, div_end, "</span>") : NULL;
        char pct[16];
        if (a && b) {
            html_text(a + 1, b, pct, sizeof(pct));
            parse_int_text(pct, &day->moon_pct);
        }
    }
    p = find_n(gt, div_end, "class=\"fc_moon_riseset\"");
    if (p) {
        const char *a = tag_close(p, div_end);
        const char *b = a ? find_n(a, div_end, "</span>") : NULL;
        char riseset[64];
        if (a && b) {
            const char *rp;
            char t1[16], t2[16];
            html_text(a + 1, b, riseset, sizeof(riseset));
            rp = riseset;
            if (parse_time_token(&rp, t1, sizeof(t1))) {
                if (!day->has_moon_rise) {
                    copy_tok(day->moon_rise, sizeof(day->moon_rise), t1);
                    day->has_moon_rise = 1;
                }
            }
            if (parse_time_token(&rp, t2, sizeof(t2))) {
                if (!day->has_moon_set) {
                    copy_tok(day->moon_set, sizeof(day->moon_set), t2);
                    day->has_moon_set = 1;
                }
            }
        }
    }
}

static void parse_sun(const char *day_s, const char *day_e, Day *day)
{
    const char *dl = find_n(day_s, day_e, "class=\"fc_daylight\"");
    const char *tag, *gt;
    char data[1024], decoded[1024];
    const char *q;
    if (!dl) {
        return;
    }
    tag = dl;
    while (tag > day_s && *tag != '<') {
        tag--;
    }
    gt = tag_close(tag, day_e);
    if (!gt) {
        return;
    }
    copy_attr_raw(tag, gt, "data-content", data, sizeof(data));
    if (!data[0]) {
        return;
    }
    html_text(data, data + strlen(data), decoded, sizeof(decoded));
    q = after_label(decoded, "Sunrise:");
    if (q) {
        parse_time_token(&q, day->sun_rise, sizeof(day->sun_rise));
    }
    q = after_label(decoded, "Sunset:");
    if (q) {
        parse_time_token(&q, day->sun_set, sizeof(day->sun_set));
    }
    q = after_label(decoded, "Sun Transit:");
    if (q) {
        parse_time_token(&q, day->sun_transit, sizeof(day->sun_transit));
    }
    q = after_label(decoded, "Civil Dark:");
    if (q) {
        parse_time_token(&q, day->civil_from, sizeof(day->civil_from));
        while (*q && (*q == '-' || is_ws((unsigned char)*q))) {
            q++;
        }
        parse_time_token(&q, day->civil_to, sizeof(day->civil_to));
    }
    q = after_label(decoded, "Nautical Dark:");
    if (q) {
        parse_time_token(&q, day->naut_from, sizeof(day->naut_from));
        while (*q && (*q == '-' || is_ws((unsigned char)*q))) {
            q++;
        }
        parse_time_token(&q, day->naut_to, sizeof(day->naut_to));
    }
    q = after_label(decoded, "Astro Dark:");
    if (q) {
        parse_time_token(&q, day->astro_from, sizeof(day->astro_from));
        while (*q && (*q == '-' || is_ws((unsigned char)*q))) {
            q++;
        }
        parse_time_token(&q, day->astro_to, sizeof(day->astro_to));
    }
}

static void parse_date(const char *day_s, const char *day_e, Day *day)
{
    const char *p = find_n(day_s, day_e, "class=\"fc_day_date\"");
    const char *gt, *end;
    char text[64];
    const char *tp;
    if (!p) {
        return;
    }
    gt = tag_close(p, day_e);
    if (!gt) {
        return;
    }
    end = find_n(gt, day_e, "</div>");
    if (!end) {
        return;
    }
    html_text(gt + 1, end, text, sizeof(text));
    tp = text;
    read_word(&tp, day->weekday, sizeof(day->weekday));
    read_word(&tp, day->day_short, sizeof(day->day_short));
}

static void parse_detail_rows(const char *day_s, const char *day_e, Day *day)
{
    const char *p = day_s;
    while (1) {
        const char *lab = find_n(p, day_e, "class=\"fc_detail_label\"");
        const char *gt, *lab_end, *ul;
        const char *next_lab;
        char label[96];
        int kind;
        if (!lab) {
            break;
        }
        gt = tag_close(lab, day_e);
        if (!gt) {
            break;
        }
        lab_end = find_n(gt, day_e, "</span></span>");
        if (!lab_end) {
            lab_end = find_n(gt, day_e, "</span>");
        }
        if (!lab_end) {
            p = gt + 1;
            continue;
        }
        html_text(gt + 1, lab_end, label, sizeof(label));
        kind = classify_label(label);
        next_lab = find_n(lab_end, day_e, "class=\"fc_detail_label\"");
        ul = find_n(lab_end, next_lab ? next_lab : day_e, "<ul");
        if (kind != ROW_UNKNOWN && ul) {
            parse_lis(ul, next_lab ? next_lab : day_e, kind, day);
            if (is_extra_row(kind)) {
                day->has_extra = 1;
            }
        }
        p = lab_end + 1;
    }
}

static int parse_day_block(const char *day_s, const char *day_e, Day *day)
{
    day_init(day);
    parse_date(day_s, day_e, day);
    parse_moon(day_s, day_e, day);
    parse_hour_ratings(day_s, day_e, day);
    parse_sun(day_s, day_e, day);
    parse_detail_rows(day_s, day_e, day);
    return day->nhours > 0;
}

static int dset(PyObject *d, const char *k, PyObject *v)
{
    int rc;
    if (!v) {
        return -1;
    }
    rc = PyDict_SetItemString(d, k, v);
    Py_DECREF(v);
    return rc;
}

static int dset_str(PyObject *d, const char *k, const char *v)
{
    if (!v || !v[0]) {
        Py_INCREF(Py_None);
        return dset(d, k, Py_None);
    }
    return dset(d, k, PyUnicode_FromString(v));
}

static int dset_int(PyObject *d, const char *k, int v)
{
    if (v == NOINT) {
        Py_INCREF(Py_None);
        return dset(d, k, Py_None);
    }
    return dset(d, k, PyLong_FromLong(v));
}

static int dset_float(PyObject *d, const char *k, double v, int present)
{
    if (!present) {
        Py_INCREF(Py_None);
        return dset(d, k, Py_None);
    }
    return dset(d, k, PyFloat_FromDouble(v));
}

static int dset_timepair(PyObject *d, const char *k, const char *a, const char *b)
{
    PyObject *lst = PyList_New(2);
    if (!lst) {
        return -1;
    }
    PyList_SET_ITEM(lst, 0, a && a[0] ? PyUnicode_FromString(a) : (Py_INCREF(Py_None), Py_None));
    PyList_SET_ITEM(lst, 1, b && b[0] ? PyUnicode_FromString(b) : (Py_INCREF(Py_None), Py_None));
    return dset(d, k, lst);
}

static PyObject *iss_to_dict(const Hour *hour)
{
    PyObject *d, *pt;
    const char *q;
    char time[16], az[16];
    int alt;
    double mag;
    if (!hour->has_iss) {
        Py_RETURN_NONE;
    }
    d = PyDict_New();
    if (!d) {
        return NULL;
    }
    q = after_label(hour->iss_raw, "Start:");
    if (q) {
        pt = PyDict_New();
        time[0] = az[0] = '\0';
        alt = NOINT;
        if (read_word(&q, time, sizeof(time))) {
            dset_str(pt, "time", time);
        }
        while (*q && *q != '(') {
            q++;
        }
        if (*q == '(') {
            q++;
            read_word(&q, az, sizeof(az));
            while (*q && *q != '-') {
                q++;
            }
            if (*q == '-') {
                q++;
                parse_int_text(q, &alt);
            }
            dset_str(pt, "direction", az);
            dset_int(pt, "altitude", alt);
        }
        dset(d, "start", pt);
    }
    q = after_label(hour->iss_raw, "Max:");
    if (q) {
        pt = PyDict_New();
        time[0] = az[0] = '\0';
        alt = NOINT;
        if (read_word(&q, time, sizeof(time))) {
            dset_str(pt, "time", time);
        }
        while (*q && *q != '(') {
            q++;
        }
        if (*q == '(') {
            q++;
            read_word(&q, az, sizeof(az));
            while (*q && *q != '-') {
                q++;
            }
            if (*q == '-') {
                q++;
                parse_int_text(q, &alt);
            }
            dset_str(pt, "direction", az);
            dset_int(pt, "altitude", alt);
        }
        dset(d, "max", pt);
    }
    q = after_label(hour->iss_raw, "End:");
    if (q) {
        pt = PyDict_New();
        time[0] = az[0] = '\0';
        alt = NOINT;
        if (read_word(&q, time, sizeof(time))) {
            dset_str(pt, "time", time);
        }
        while (*q && *q != '(') {
            q++;
        }
        if (*q == '(') {
            q++;
            read_word(&q, az, sizeof(az));
            while (*q && *q != '-') {
                q++;
            }
            if (*q == '-') {
                q++;
                parse_int_text(q, &alt);
            }
            dset_str(pt, "direction", az);
            dset_int(pt, "altitude", alt);
        }
        dset(d, "end", pt);
    }
    q = after_label(hour->iss_raw, "Magnitude:");
    if (q && parse_double_text(q, &mag)) {
        dset(d, "magnitude", PyFloat_FromDouble(mag));
    }
    return d;
}

static PyObject *hour_to_dict(const Hour *hour, int metric, int include_extra)
{
    PyObject *d = PyDict_New();
    PyObject *wind;
    PyObject *temp;
    double vis, wspd;
    if (!d) {
        return NULL;
    }
    dset_str(d, "conditions", hour->conditions);
    dset_int(d, "total-clouds", hour->total_clouds);
    dset_int(d, "low-clouds", hour->low_clouds);
    dset_int(d, "mid-clouds", hour->mid_clouds);
    dset_int(d, "high-clouds", hour->high_clouds);
    vis = hour->visibility;
    if (hour->has_vis && metric) {
        vis = round2((double)((int)vis) * MILES_TO_KM);
    } else if (hour->has_vis) {
        vis = round2(vis);
    }
    dset_float(d, "visibility", vis, hour->has_vis);
    dset_int(d, "fog", hour->fog);
    dset_str(d, "prec-type", hour->prec_type[0] ? hour->prec_type : "none");
    dset_int(d, "prec-probability", hour->prec_prob);
    dset_float(d, "prec-amount", hour->prec_amt, hour->has_prec_amt);
    wind = PyDict_New();
    wspd = hour->wind_speed;
    if (hour->has_wind && metric) {
        wspd = round2((double)((int)wspd) * MILES_TO_KM);
    } else if (hour->has_wind) {
        wspd = round2(wspd);
    }
    dset_float(wind, "speed", wspd, hour->has_wind);
    dset_str(wind, "direction", hour->wind_dir);
    dset_int(wind, "degrees", hour->has_wind_deg ? hour->wind_deg : NOINT);
    dset(d, "wind", wind);
    dset_str(d, "frost", hour->frost == 1 ? "frost" : (hour->frost == 0 ? "none" : NULL));
    temp = PyDict_New();
    dset_int(temp, "general", hour->temp);
    dset_int(temp, "feels-like", hour->feels);
    dset_int(temp, "dew-point", hour->dew);
    dset(d, "temperature", temp);
    dset_int(d, "rel-humidity", hour->humidity);
    dset_int(d, "pressure", hour->pressure);
    dset_int(d, "ozone", hour->ozone);
    dset(d, "iss", iss_to_dict(hour));
    if (include_extra) {
        PyObject *extra = PyDict_New();
        PyObject *metno = PyDict_New();
        PyObject *t7 = PyDict_New();
        dset_int(metno, "total-clouds", hour->metno_total);
        dset_int(metno, "low-clouds", hour->metno_low);
        dset_int(metno, "mid-clouds", hour->metno_mid);
        dset_int(metno, "high-clouds", hour->metno_high);
        dset_int(t7, "cloud-cover", hour->t7_cloud);
        dset_int(t7, "seeing", hour->t7_seeing);
        dset_int(t7, "lifted-index", hour->t7_lifted);
        dset_int(t7, "transparency", hour->t7_trans);
        dset(extra, "metno", metno);
        dset(extra, "timer", t7);
        dset(d, "extra", extra);
    }
    return d;
}

static PyObject *day_to_dict(const Day *day, int metric)
{
    PyObject *d = PyDict_New();
    PyObject *date, *sun, *moon, *phase, *mer, *hours;
    int i;
    double dist;
    if (!d) {
        return NULL;
    }
    date = PyDict_New();
    dset_str(date, "long", day->weekday);
    dset_str(date, "short", day->day_short);
    dset(d, "date", date);

    sun = PyDict_New();
    dset_str(sun, "rise", day->sun_rise);
    dset_str(sun, "set", day->sun_set);
    dset_str(sun, "transit", day->sun_transit);
    dset_timepair(sun, "civil-dark", day->civil_from, day->civil_to);
    dset_timepair(sun, "nautical-dark", day->naut_from, day->naut_to);
    dset_timepair(sun, "astro-dark", day->astro_from, day->astro_to);
    dset(d, "sun", sun);

    moon = PyDict_New();
    dset_str(moon, "rise", day->has_moon_rise ? day->moon_rise : NULL);
    dset_str(moon, "set", day->has_moon_set ? day->moon_set : NULL);
    dset_str(moon, "rise-date", day->moon_rise_date);
    dset_str(moon, "set-date", day->moon_set_date);
    phase = PyDict_New();
    dset_str(phase, "name", day->moon_phase);
    dset_int(phase, "percentage", day->moon_pct);
    dset(moon, "phase", phase);
    mer = PyDict_New();
    dset_str(mer, "time", day->mer_time);
    dset_str(mer, "date", day->mer_date);
    dset_float(mer, "altitude", day->mer_alt, day->has_mer_alt);
    dist = day->mer_dist_miles;
    if (day->has_mer_dist && metric) {
        dist = round2(day->mer_dist_miles * MILES_TO_KM);
    } else if (day->has_mer_dist) {
        dist = round2(dist);
    }
    dset_float(mer, "distance", dist, day->has_mer_dist);
    dset_str(mer, "distance-unit", metric ? "km" : "miles");
    dset(moon, "meridian", mer);
    dset(d, "moon", moon);

    hours = PyDict_New();
    for (i = 0; i < day->nhours; i++) {
        PyObject *hd = hour_to_dict(&day->hours[i], metric, day->has_extra);
        const char *key = day->hours[i].hour[0] ? day->hours[i].hour : "??";
        if (!hd) {
            Py_DECREF(hours);
            Py_DECREF(d);
            return NULL;
        }
        PyDict_SetItemString(hours, key, hd);
        Py_DECREF(hd);
    }
    dset(d, "hours", hours);
    return d;
}

static int parse_header(const char *html, const char *end, PyObject *out)
{
    const char *h1 = find_n(html, end, "<h1>");
    const char *h1e, *p;
    char h1text[512];
    char loc[400], lat[32], lon[32];
    char mag[32], bortle[48], bright[32], artif[32];
    const char *sq, *h2, *h2e;
    char h2text[256];
    PyObject *location, *sky, *brightness, *artif_d, *gen, *last, *fc;
    char gen_date[16], gen_time[16], from_day[16], to_day[16], tz[32];
    const char *q;
    int bortle_n = NOINT;
    double mag_v = 0, bright_v = 0, artif_v = 0;
    int has_mag = 0, has_bright = 0, has_artif = 0;

    loc[0] = lat[0] = lon[0] = '\0';
    if (h1) {
        h1e = find_n(h1, end, "</h1>");
        if (h1e) {
            char *lp, *rp, *comma;
            html_text(h1 + 4, h1e, h1text, sizeof(h1text));
            p = h1text;
            if (strncmp(p, "Forecast for ", 13) == 0) {
                p += 13;
            }
            copy_tok(loc, sizeof(loc), p);
            lp = strrchr(loc, '(');
            rp = strrchr(loc, ')');
            if (lp && rp && rp > lp) {
                *lp = '\0';
                trim_inplace(loc);
                *rp = '\0';
                comma = strchr(lp + 1, ',');
                if (comma) {
                    *comma = '\0';
                    copy_tok(lat, sizeof(lat), lp + 1);
                    copy_tok(lon, sizeof(lon), comma + 1);
                    trim_inplace(lat);
                    trim_inplace(lon);
                }
            } else {
                trim_inplace(loc);
            }
        }
    }

    location = PyDict_New();
    dset_str(location, "name", loc);
    dset_str(location, "latitude", lat);
    dset_str(location, "longitude", lon);
    if (dset(out, "location", location) < 0) {
        return -1;
    }

    mag[0] = bortle[0] = bright[0] = artif[0] = '\0';
    sq = find_n(html, end, "Est. Sky Quality");
    if (sq) {
        const char *limit = sq + 800 < end ? sq + 800 : end;
        const char *cur = sq;
        if (find_n(cur, limit, "<strong>") &&
            (cur = find_n(cur, limit, "<strong>")) != NULL) {
            const char *se = find_n(cur + 8, limit, "</strong>");
            if (se) {
                html_text(cur + 8, se, mag, sizeof(mag));
                cur = se + 9;
            }
        }
        if ((cur = find_n(cur, limit, "<strong>")) != NULL) {
            const char *se = find_n(cur + 8, limit, "</strong>");
            if (se) {
                html_text(cur + 8, se, bortle, sizeof(bortle));
                cur = se + 9;
            }
        }
        if ((cur = find_n(cur, limit, "<strong>")) != NULL) {
            const char *se = find_n(cur + 8, limit, "</strong>");
            if (se) {
                html_text(cur + 8, se, bright, sizeof(bright));
                cur = se + 9;
            }
        }
        if ((cur = find_n(cur, limit, "<strong>")) != NULL) {
            const char *se = find_n(cur + 8, limit, "</strong>");
            if (se) {
                html_text(cur + 8, se, artif, sizeof(artif));
            }
        }
    }
    has_mag = parse_double_text(mag, &mag_v);
    {
        const char *bp = bortle;
        if (strncmp(bp, "Class ", 6) == 0) {
            bp += 6;
        }
        parse_int_text(bp, &bortle_n);
    }
    has_bright = parse_double_text(bright, &bright_v);
    has_artif = parse_double_text(artif, &artif_v);

    sky = PyDict_New();
    dset_float(sky, "magnitude", mag_v, has_mag);
    dset_int(sky, "bortle_class", bortle_n);
    brightness = PyDict_New();
    dset_float(brightness, "value", bright_v, has_bright);
    dset_str(brightness, "unit", "mcd/m2");
    dset(sky, "brightness", brightness);
    artif_d = PyDict_New();
    dset_float(artif_d, "value", artif_v, has_artif);
    dset_str(artif_d, "unit", "ucd/m2");
    dset(sky, "artif-brightness", artif_d);
    if (dset(out, "sky-quality", sky) < 0) {
        return -1;
    }

    gen_date[0] = gen_time[0] = from_day[0] = to_day[0] = tz[0] = '\0';
    h2 = find_n(html, end, "<h2>");
    if (h2) {
        h2e = find_n(h2, end, "</h2>");
        if (h2e) {
            html_text(h2 + 4, h2e, h2text, sizeof(h2text));
            q = after_label(h2text, "Generated:");
            if (q) {
                read_word(&q, gen_date, sizeof(gen_date));
                read_word(&q, gen_time, sizeof(gen_time));
                {
                    size_t n = strlen(gen_time);
                    if (n && gen_time[n - 1] == '.') {
                        gen_time[n - 1] = '\0';
                    }
                }
            }
            q = after_label(h2text, "Forecast:");
            if (q) {
                read_word(&q, from_day, sizeof(from_day));
                /* skip "to" */
                {
                    char tmp[8];
                    read_word(&q, tmp, sizeof(tmp));
                }
                read_word(&q, to_day, sizeof(to_day));
                {
                    size_t n = strlen(to_day);
                    if (n && to_day[n - 1] == '.') {
                        to_day[n - 1] = '\0';
                    }
                }
            }
            q = after_label(h2text, "Timezone:");
            if (q) {
                read_word(&q, tz, sizeof(tz));
            }
        }
    }
    gen = PyDict_New();
    last = PyDict_New();
    fc = PyDict_New();
    dset_str(last, "date", gen_date);
    dset_str(last, "time", gen_time);
    dset_str(fc, "from-day", from_day);
    dset_str(fc, "to-day", to_day);
    dset(gen, "last-gen", last);
    dset(gen, "forecast", fc);
    dset_str(gen, "timezone", tz);
    if (dset(out, "gen-info", gen) < 0) {
        return -1;
    }
    return 0;
}

static PyObject *parse_html(PyObject *self, PyObject *args, PyObject *kwargs)
{
    Py_buffer buf;
    int metric = 1;
    static char *kwlist[] = {"html", "metric", NULL};
    const char *html, *end;
    const char *starts[MAX_DAYS];
    int ndays = 0, i;
    const char *p;
    PyObject *out, *forecast, *units;
    Day *days;

    (void)self;
    buf.buf = NULL;
    buf.len = 0;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "y*|p", kwlist, &buf, &metric)) {
        return NULL;
    }
    html = (const char *)buf.buf;
    end = html + buf.len;

    p = html;
    while (ndays < MAX_DAYS) {
        const char *hit = find_n(p, end, "class=\"fc_day\"");
        const char *tag;
        if (!hit) {
            break;
        }
        tag = hit;
        while (tag > html && *tag != '<') {
            tag--;
        }
        starts[ndays++] = tag;
        p = hit + 14;
    }
    if (ndays == 0) {
        PyBuffer_Release(&buf);
        PyErr_SetString(ParseError, "no forecast days found; is this a Clear Outside forecast page?");
        return NULL;
    }

    days = (Day *)PyMem_Calloc((size_t)ndays, sizeof(Day));
    if (!days) {
        PyBuffer_Release(&buf);
        return PyErr_NoMemory();
    }
    for (i = 0; i < ndays; i++) {
        const char *ds = starts[i];
        const char *de = (i + 1 < ndays) ? starts[i + 1] : end;
        parse_day_block(ds, de, &days[i]);
    }

    out = PyDict_New();
    if (!out) {
        PyMem_Free(days);
        PyBuffer_Release(&buf);
        return NULL;
    }
    if (parse_header(html, end, out) < 0) {
        Py_DECREF(out);
        PyMem_Free(days);
        PyBuffer_Release(&buf);
        return NULL;
    }

    units = PyDict_New();
    dset_str(units, "visibility", metric ? "km" : "miles");
    dset_str(units, "wind-speed", metric ? "km/h" : "mph");
    dset_str(units, "temperature", "C");
    dset_str(units, "precipitation", "mm");
    dset_str(units, "pressure", "mb");
    dset_str(units, "ozone", "du");
    dset_str(units, "moon-distance", metric ? "km" : "miles");
    dset_str(units, "sky-brightness", "mcd/m2");
    dset_str(units, "artificial-brightness", "ucd/m2");
    dset(out, "units", units);

    forecast = PyDict_New();
    for (i = 0; i < ndays; i++) {
        char key[16];
        PyObject *dd = day_to_dict(&days[i], metric);
        if (!dd) {
            Py_DECREF(forecast);
            Py_DECREF(out);
            PyMem_Free(days);
            PyBuffer_Release(&buf);
            return NULL;
        }
        PyOS_snprintf(key, sizeof(key), "day-%d", i);
        PyDict_SetItemString(forecast, key, dd);
        Py_DECREF(dd);
    }
    dset(out, "forecast", forecast);

    PyMem_Free(days);
    PyBuffer_Release(&buf);
    return out;
}

static PyMethodDef methods[] = {
    {"parse_html", (PyCFunction)(void (*)(void))parse_html, METH_VARARGS | METH_KEYWORDS,
     "parse_html(html: bytes, metric: bool = True) -> dict"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "clear_outside_apy._parser",
    "C parser for clearoutside.com forecast HTML",
    -1,
    methods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC PyInit__parser(void)
{
    PyObject *m = PyModule_Create(&moduledef);
    if (!m) {
        return NULL;
    }
    ParseError = PyErr_NewException("clear_outside_apy._parser.ParseError", NULL, NULL);
    if (!ParseError) {
        Py_DECREF(m);
        return NULL;
    }
    Py_INCREF(ParseError);
    if (PyModule_AddObject(m, "ParseError", ParseError) < 0) {
        Py_DECREF(ParseError);
        Py_DECREF(m);
        return NULL;
    }
    return m;
}
