// import moment from 'moment';
import moment from 'moment-timezone'

export function datetimeToLocal(d, fmt) {
    try {
        let tz = Intl.DateTimeFormat().resolvedOptions().timeZone
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

        return d.format(fmt) + tz
    } catch (e) {
        return d
    }
}



export function humanBytes(bytes, si) {
    var thresh = si ? 1000 : 1024;
    if (Math.abs(bytes) < thresh) {
        return bytes + ' B';
    }
    var units = si
        ? ['kB','MB','GB','TB','PB','EB','ZB','YB']
        : ['KiB','MiB','GiB','TiB','PiB','EiB','ZiB','YiB'];
    var u = -1;
    do {
        bytes /= thresh;
        ++u;
    } while(Math.abs(bytes) >= thresh && u < units.length - 1);
    return bytes.toFixed(1)+' '+units[u];
}
