def lin_reg(x1, x2):
    return 191.3642 + (x1 * 19.59733806) + (x2 * 7.05360083)

def pricePrediction(color_area, print_area):
    prediction = lin_reg(color_area, print_area)
    if prediction < 300 and color_area == 0 :
        prediction = 300
    if prediction < 500 and color_area != 0 :
        prediction = 500
    return (round(prediction))
