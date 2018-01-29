// Override autoIncrement to allow pointInterval: 'month' and 'year'
(function (H) {
    var pick = H.pick,
        useUTC = H.getOptions().global.useUTC,
        setMonth = useUTC ? 'setUTCMonth' : 'setMonth',
        getMonth = useUTC ? 'getUTCMonth' : 'getMonth',
        setFullYear = useUTC ? 'setUTCFullYear' : 'setFullYear',
        getFullYear = useUTC ? 'getUTCFullYear' : 'getFullYear';

    H.Series.prototype.autoIncrement = function () {

        var options = this.options,
            xIncrement = this.xIncrement,
            date,
            pointInterval,
            pointIntervalUnit = options.pointIntervalUnit;

        xIncrement = pick(xIncrement, options.pointStart, 0);

        this.pointInterval = pointInterval = pick(this.pointInterval, options.pointInterval, 1);

        // Added code for pointInterval strings
        if (pointIntervalUnit === 'month' || pointIntervalUnit === 'year') {
            date = new Date(xIncrement);
            date = (pointIntervalUnit === 'month') ?
                +date[setMonth](date[getMonth]() + pointInterval) :
                +date[setFullYear](date[getFullYear]() + pointInterval);
            pointInterval = date - xIncrement;
        }

        this.xIncrement = xIncrement + pointInterval;
        return xIncrement;
    };
}(Highcharts));