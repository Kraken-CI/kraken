export class TestCaseResults {
    static resultColor(result) {
        var mapping = {
            0: '#FF8800',
            1: '#008800',
            2: '#FF2200',
            3: '#880000',
            4: '#888888',
            5: '#444444',
        }
        return mapping[result]
    }

    static formatResult(result) {
        var resultMapping = {
            0: {
                style: 'color: ' + TestCaseResults.resultColor(result) + ';',
                txt: 'Not run',
            },
            1: {
                style: 'color: ' + TestCaseResults.resultColor(result) + ';',
                txt: 'Passed',
            },
            2: {
                style: 'color: ' + TestCaseResults.resultColor(result) + ';',
                txt: 'Failed',
            },
            3: {
                style: 'color: ' + TestCaseResults.resultColor(result) + ';',
                txt: 'ERROR',
            },
            4: {
                style: 'color: ' + TestCaseResults.resultColor(result) + ';',
                txt: 'Disabled',
            },
            5: {
                style: 'color: ' + TestCaseResults.resultColor(result) + ';',
                txt: 'Unsupported',
            },
        }

        let val = resultMapping[result]

        return '<span style="' + val.style + '">' + val.txt + '</span>'
    }

    static resultToTxt(result) {
        var resultMapping = {
            0: 'Not run',
            1: 'Passed',
            2: 'Failed',
            3: 'ERROR',
            4: 'Disabled',
            5: 'Unsupported',
        }
        return resultMapping[result]
    }
}
