import { DateTime } from 'luxon'

export function datetimeToLocal(d, fmt) {
    try {
        let tz = Intl.DateTimeFormat().resolvedOptions().timeZone
        if (!tz) {
            tz = DateTime.local().zoneName
        }
        if (tz) {
            d = DateTime.fromISO(d).setZone(tz)
            tz = ''
        } else {
            d = DateTime.fromISO(d)
            tz = ' UTC'
        }

        if (fmt === 'ago') {
            return d.toRelative()
        } else {
            if (!fmt) {
                fmt = 'yyyy-LL-dd HH:mm:ss'
            }

            return d.toFormat(fmt) + tz
        }
    } catch (e) {
        return d
    }
}

export function humanBytes(bytes, si) {
    const thresh = si ? 1000 : 1024
    if (Math.abs(bytes) < thresh) {
        return bytes + ' B'
    }
    const units = si
        ? ['kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
        : ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
    let u = -1
    do {
        bytes /= thresh
        ++u
    } while (Math.abs(bytes) >= thresh && u < units.length - 1)
    return bytes.toFixed(1) + ' ' + units[u]
}
