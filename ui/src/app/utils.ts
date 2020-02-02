//import moment from 'moment';
import moment from "moment-timezone";

export function datetimeToLocal(d, fmt) {
    try {
        var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (!tz) {
            tz = moment.tz.guess()
        }
        if (tz) {
            d = moment(d).tz(tz)
            tz = ''
        } else {
            d = moment(d)
            tz = ' UTC'
        }

        if (!fmt) {
            fmt = 'YYYY-MM-DD HH:mm:ss'
        }

        return d.format(fmt) + tz;
    } catch(e) {
        return d;
    }
}
