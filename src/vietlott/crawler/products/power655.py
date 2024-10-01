import os 
import math
import gspread  
from oauth2client.service_account import ServiceAccountCredentials

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict

import cattrs
import pandas as pd
from bs4 import BeautifulSoup
from loguru import logger


from vietlott.config.products import ProductConfig
from vietlott.crawler import collections_helper
from vietlott.crawler.products.base import BaseProduct
from vietlott.crawler.requests_helper import config as requests_config, fetch
from vietlott.crawler.schema.requests import RequestPower655, ORenderInfoCls


class ProductPower655(BaseProduct):
    name = "power_655"
    url = "https://vietlott.vn/ajaxpro/Vietlott.PlugIn.WebParts.Game655CompareWebPart,Vietlott.PlugIn.WebParts.ashx"
    page_to_run = 1  # roll every 2 days

    stored_data_dtype = {
        "date": str,
        "id": str,
        "result": "list",
        "page": int,
        "process_time": str,
    }

    orender_info_default = ORenderInfoCls(
        SiteId="main.frontend.vi",
        SiteAlias="main.vi",
        UserSessionId="",
        SiteLang="en",
        IsPageDesign=False,
        ExtraParam1="",
        ExtraParam2="",
        ExtraParam3="",
        SiteURL="",
        WebPage=None,
        SiteName="Vietlott",
        OrgPageAlias=None,
        PageAlias=None,
        RefKey=None,
        FullPageAlias=None,
    )

    org_body = RequestPower655(
        ORenderInfo=orender_info_default,
        Key="23bbd666",
        GameDrawId="",
        ArrayNumbers=[["" for _ in range(18)] for _ in range(5)],
        CheckMulti=False,
        PageIndex=0,
    )
    org_params = {}

    product_config: Optional[ProductConfig] = None

    def __init__(self):
        super(ProductPower655, self).__init__()

    def process_result(self, params, body, res_json, task_data) -> List[Dict]:
        """
        process 645/655 result
        :param params:
        :param body:
        :param res_json:
        :param task_data:
        :return: list of dict data {date, id, result, page, process_time}
        """
        soup = BeautifulSoup(res_json.get("value", {}).get("HtmlContent"), "lxml")
        data = []
        for i, tr in enumerate(soup.select("table tr")):
            if i == 0:
                continue
            tds = tr.find_all("td")
            row = {}

            row["date"] = datetime.strptime(tds[0].text, "%d/%m/%Y").strftime(
                "%Y-%m-%d"
            )
            row["id"] = tds[1].text

            # last number of special
            row["result"] = [
                int(span.text)
                for span in tds[2].find_all("span")
                if span.text.strip() != "|"
            ]
            row["page"] = body.get("PageIndex", -1)
            row["process_time"] = datetime.now().isoformat()

            data.append(row)
        return data

    def crawl(self, run_date_str: str, index_from: int = 0, index_to: int = 1):
        """
        spawn multiple worker to get data from vietlott
        each worker craw a list of dates

        crawl from [index_from, index_to)
        :param product_config:
        :param index_from: latest page we want to crawl, default = 0 (1 page)
        :param index_to: the earliest page we want to crawl, default = 1 (1 page)
            if null then using default index_to in product's config
        """
        if index_to is None:
            index_to = self.product_config.default_index_to

        if index_to == index_from:
            index_to += 1

        pool = ThreadPoolExecutor(self.product_config.num_thread)
        page_per_task = math.ceil((index_to - index_from) / self.product_config.num_thread)
        tasks = collections_helper.chunks_iter(
            [
                {
                    "task_id": i,
                    "task_data": {
                        "params": {},
                        "body": {"PageIndex": i},
                        "run_date_str": run_date_str,
                    },
                }
                for i in range(index_from, index_to+1)
            ],
            page_per_task,
        )

        logger.info(f"there are {index_to - index_from} pages, from {index_from}->{index_to}, {page_per_task} page per task")
        fetch_fn = fetch.fetch_wrapper(
            self.url,
            requests_config.headers,
            self.org_params,
            cattrs.unstructure(self.org_body),
            self.process_result,
            self.cookies
        )


       

        results = pool.map(fetch_fn, tasks)
        # gcp_credentials = os.getenv("GOOGLE_CREDENTIALS")
        # creds_dict = json.loads(gcp_credentials)
        # scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        # # creds = ServiceAccountCredentials.from_json_keyfile_name("src/creds.json", scope)
        # creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        # client = gspread.authorize(creds)

        # sheetname = "Camlot"
        # sheet  = client.open(sheetname).sheet1
        # sheet655  = client.open(sheetname).worksheet("Mega 655")
        # sheet645  = client.open(sheetname).worksheet("Mega 645")
        # sheet3d  = client.open(sheetname).worksheet("Max3D")

        # rv = sheet.row_values(2)
        # logger.info(f"dick data: {rv}")


        # flatten results, as it is 3 level deep
        date_dict = defaultdict(list)
        for l1 in results:
            for l2 in l1:
                for row in l2:
                    date_dict[row["date"]].append(row)

        list_data = []
        for date, date_items in date_dict.items():
            list_data += date_items

        df_crawled = pd.DataFrame(list_data)
        logger.info(
            f'crawled data date: min={df_crawled["date"].min()}, max={df_crawled["date"].max()}'
            + f' id min={df_crawled["id"].min()}, max={df_crawled["id"].max()}'
            + f", records={len(df_crawled)}"
        )

        df_take = None  # Initialize df_take with a default value
        # store data
        if self.product_config.raw_path.exists():
            current_data = pd.read_json(
                self.product_config.raw_path, lines=True, dtype=self.stored_data_dtype
            )
            logger.info(
                f'current data date min={current_data["date"].min()}, max={current_data["date"].max()}'
                + f' id min={current_data["id"].min()}, max={current_data["id"].max()}'
                + f", records={len(current_data)}"
            )
            df_take = df_crawled[~df_crawled["id"].isin(current_data["id"])]

            logger.info(f'Last result: {df_take["id"].max()}, result={df_take["result"].max()}')

                # od = sheet.row_values((rv - 1))
                # if od[0] == df_take["id"].max():
                #     logger.info(f'duplicate last result: {od[0]}')
                # else:
                #     sheet.insert_row(insertrow, rv)


            # sheet.append_row(insertrow)
            # logger.info(f'row data: {insertrow}')


            df_final = pd.concat([current_data, df_take], axis="rows")  
        else:
            df_final = df_crawled

        df_final = df_final.sort_values(by=["date", "id"])
    

        ids = df_crawled["id"]
        rss = df_crawled["result"]
        dss = df_crawled["date"]
        l = len(ids)
        vip = l - 1
        ar = []

        logger.info(f'total ID crawl: {len(ids)}')
        logger.info(f'Dick Iz: {self.name}')

        # if self.name == "keno":
        #     for di in range(l):
        #         # rv = sheet.row_count
        #         v = vip - di
        #         r = di + 2

        #         rs = rss[v]
        #         ds = dss[v]
        #         idick = ids[v]


        #         # logger.info(f'shit ID: {idick}')
        #         # logger.info(f'shit Date: {ds}')
        #         # logger.info(f'shit RESULTS: {rs}')

        #         insertrow = [ids[v], ds]
        #         for x in range(80):
        #             if (x + 1) in rs:
        #                 insertrow.append('')
        #             else:
        #                 insertrow.append((x + 1))
                
        #         # sheet.insert_row(insertrow, r)
        #         ar.append(insertrow)
        #         # logger.info(f'Insert data: {insertrow}')
        #     sheet.resize(1)
        #     sheet.resize(2)
        #     sheet.insert_rows(ar, 2)

        # elif self.name == "power_655":
        #     rss = current_data["result"]
        #     dss = current_data["date"]
        #     ids = current_data["id"]
        #     l = len(ids)
        #     vip = l - 1
        #     for di in range(l):
        #         v = vip - di
        #         r = di + 2

        #         rs = rss[di]
        #         ds = dss[di]
        #         idick = ids[di]


        #         # logger.info(f'shit ID: {idick}')
        #         # logger.info(f'shit Date: {ds}')
        #         # logger.info(f'shit RESULTS: {rs}')

        #         insertrow = [ids[di], ds]
        #         for x in range(55):
        #             if (x + 1) in rs:
        #                 insertrow.append('')
        #             else:
        #                 insertrow.append((x + 1))
                
        #         ar.append(insertrow)
        #     sheet655.resize(1)
        #     sheet655.resize(2)
        #     sheet655.insert_rows(ar, 2)
        # elif self.name == "power_645":
        #     rss = current_data["result"]
        #     dss = current_data["date"]
        #     ids = current_data["id"]
        #     l = len(ids)
        #     vip = l - 1
        #     for di in range(l):
        #         v = vip - di
        #         r = di + 2

        #         rs = rss[di]
        #         ds = dss[di]
        #         idick = ids[di]


        #         # logger.info(f'shit ID: {idick}')
        #         # logger.info(f'shit Date: {ds}')
        #         # logger.info(f'shit RESULTS: {rs}')

        #         insertrow = [ids[di], ds]
        #         for x in range(45):
        #             if (x + 1) in rs:
        #                 insertrow.append('')
        #             else:
        #                 insertrow.append((x + 1))
                
        #         ar.append(insertrow)
        #     sheet645.resize(1)
        #     sheet645.resize(2)
        #     sheet645.insert_rows(ar, 2)

        # elif self.name == "max3d":
        #     logger.info(f'shit: ' + current_data['number01'])
            # rss = current_data["result"]
            # dss = current_data["date"]
            # ids = current_data["id"]
            # l = len(ids)
            # vip = l - 1
            # for di in range(l):
            #     v = vip - di
            #     r = di + 2

            #     rs = rss[di]
            #     ds = dss[di]
            #     idick = ids[di]


            #     insertrow = [ids[di], ds]
            #     insertrow.append(rss[0])
                
            #     ar.append(insertrow)

            # sheet3d.resize(1)
            # sheet3d.resize(2)
            # sheet3d.insert_rows(ar, 2)
        


        logger.info(
            f'final data min_date={df_final["date"].min()}, max_date={df_final["date"].max()}'
            + f", records={len(df_final)}"
        )
        df_final.to_json(
            self.product_config.raw_path.absolute(), orient="records", lines=True
        )
        logger.info(f"wrote to file {self.product_config.raw_path.absolute()}")
