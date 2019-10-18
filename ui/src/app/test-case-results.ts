export class TestCaseResults {

    static formatResult(result) {
        var resultMapping = {
            0: {style: 'color: #FF8800;', txt: 'Not run'},
            1: {style: 'color: #008800;', txt: 'Passed'},
            2: {style: 'color: #FF2200;', txt: 'Failed'},
            3: {style: 'color: #880000;', txt: 'ERROR'},
            4: {style: 'color: #888888;', txt: 'Disabled'},
            5: {style: 'color: #444444;', txt: 'Unsupported'},
        };

        let val = resultMapping[result]

        return '<span style="' + val.style + '">' + val.txt + '</span>';
    }

    static resultToTxt(result) {
        var resultMapping = {
            0: 'Not run',
            1: 'Passed',
            2: 'Failed',
            3: 'ERROR',
            4: 'Disabled',
            5: 'Unsupported',
        };
        return resultMapping[result];
    }
}
