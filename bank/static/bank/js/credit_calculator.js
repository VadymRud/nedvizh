$('#c_calc_firstmoney').change(function(){ proceed_credit_calculator(); });
$('#c_calc_years').change(function(){ proceed_credit_calculator(); });
$('#c_calc_rate').change(function(){ proceed_credit_calculator(); });

function proceed_credit_calculator() {
    
    var fisrt_part = parseInt($('#item_price').val())*parseInt($('#c_calc_firstmoney').val())/100;
    $('#fisrt_part').html(number_format(fisrt_part,0,'.',' '));
    
    var credit_summ = parseInt($('#item_price').val()) - fisrt_part;
    $('#credit_summ').html(number_format(credit_summ,0,'.',' '));
    
    var credit_proc = parseFloat($('#c_calc_rate').val()/100);
    var credit_months = parseInt($('#c_calc_years').val()*12);
    
    var month_summ = (credit_summ * credit_proc / credit_months)/(1 - Math.pow((1 + credit_proc / credit_months),1-credit_months))
    $('#month_summ').html(number_format(month_summ,0,'.',' '));
    
    var back_summ = month_summ * credit_months;
    $('#back_summ').html(number_format(back_summ,0,'.',' '));
    
}

proceed_credit_calculator();

function number_format (number, decimals, dec_point, thousands_sep)
{
    var exponent = "";
    var numberstr = number.toString ();
    var eindex = numberstr.indexOf ("e");
    if (eindex > -1)
    {
        exponent = numberstr.substring (eindex);
        number = parseFloat (numberstr.substring (0, eindex));
    }

    if (decimals != null)
    {
        var temp = Math.pow (10, decimals);
        number = Math.round (number * temp) / temp;
    }
    var sign = number < 0 ? "-" : "";
    var integer = (number > 0 ?
    Math.floor (number) : Math.abs (Math.ceil (number))).toString ();

    var fractional = number.toString ().substring (integer.length + sign.length);
    dec_point = dec_point != null ? dec_point : ".";
    fractional = decimals != null && decimals > 0 || fractional.length > 1 ? (dec_point + fractional.substring (1)) : "";
    if (decimals != null && decimals > 0)
    {
        for (i = fractional.length - 1, z = decimals; i < z; ++i) fractional += "0";
    }

    thousands_sep = (thousands_sep != dec_point || fractional.length == 0) ? thousands_sep : null;
    if (thousands_sep != null && thousands_sep != "")
    {
        for (i = integer.length - 3; i > 0; i -= 3)
            integer = integer.substring (0 , i) + thousands_sep + integer.substring (i);
    }
    
    return sign + integer + fractional + exponent;
}