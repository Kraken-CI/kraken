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

export function showErrorBox(msgSrv, err, summary) {
    let msg = err.statusText
    if (err.error && err.error.detail) {
        msg = err.error.detail
    }
    msgSrv.add({
        severity: 'error',
        summary: summary,
        detail: 'Error: ' + msg,
        life: 10000,
    })
}

export function pick<T extends {}, K extends keyof T>(obj: T, ...keys: K[]) {
  return Object.fromEntries(
    keys
    .filter(key => key in obj)
    .map(key => [key, obj[key]])
  )
}

export function replaceEntityIntoLink(msg: string) {
    // turn <Entity 123> into links
    const regex = /<([A-Za-z]+)\ (\d+)(>|[,\ >]+?.*?>)/g;
    const m1 = msg.matchAll(regex)
    if (m1) {
        const m2 = [...m1]
        for (const m of m2) {
            let txt = m[0]
            txt = txt.replace('<', '&lt;')
            txt = txt.replace('>', '&gt;')
            let entity = m[1].toLowerCase()
            switch (entity) {
            case 'run': entity = 'runs'; break;
            case 'branch': entity = 'branches'; break;
            case 'flow': entity = 'flows'; break;
            default: entity = null
            }
            let newTxt = ''
            if (entity) {
                const entId = m[2]
                newTxt = `<a href="/${entity}/${entId}" target="blank" style="color: #5bb7ff;">${txt}</a>`
            } else {
                newTxt = m[0].replaceAll('<', '&lt;').replaceAll('>', '&gt;')
            }
            msg = msg.replace(m[0], newTxt)
        }
    }
    // msg = msg.replaceAll('<', '&lt;')
    // msg = msg.replaceAll('>', '&gt;')

    return msg
}
