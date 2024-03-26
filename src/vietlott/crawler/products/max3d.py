from vietlott.crawler.products.power655 import ProductPower655
from vietlott.crawler.schema.requests import Max3D


class ProductMax3D(ProductPower655):
    name = "max3d"
    url = "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.GameMax3DCompareWebPart,Vietlott.PlugIn.WebParts.ashx"
    org_body = Max3D(
        ORenderInfo=ProductPower655.orender_info_default,
        Key="7d861b56",  # dick
        GameDrawId="",
        number01=0,
        number02=0,
        CheckMulti=False,
        PageIndex=0
    )

