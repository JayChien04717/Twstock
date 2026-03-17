"""
AI 台股分析師 — 族群資金輪動分析模組
"""
import pandas as pd
import numpy as np
from config import SECTOR_GROUPS


class SectorRotation:
    """按產業族群追蹤三大法人資金輪動"""

    def __init__(self, stock_info_df: pd.DataFrame = None):
        """
        stock_info_df: 股票總覽 DataFrame (需包含 stock_id, industry_category)
        """
        self.stock_info = stock_info_df
        self._sector_map = None

    def _build_sector_map(self) -> dict:
        """建立 stock_id → 族群 對照表"""
        if self._sector_map is not None:
            return self._sector_map

        if self.stock_info is None or len(self.stock_info) == 0:
            return {}

        # 反轉 SECTOR_GROUPS: industry_category → 族群名
        cat_to_group = {}
        for group_name, categories in SECTOR_GROUPS.items():
            for cat in categories:
                cat_to_group[cat] = group_name

        # stock_id → 族群
        self._sector_map = {}
        for _, row in self.stock_info.iterrows():
            sid = row["stock_id"]
            cat = row.get("industry_category", "")
            self._sector_map[sid] = cat_to_group.get(cat, "其他")

        return self._sector_map

    def analyze(self, institutional_all_df: pd.DataFrame, days_list: list = None) -> dict:
        """
        族群資金輪動分析
        institutional_all_df: 所有股票的三大法人買賣超
        days_list: 分析天數列表, e.g. [1, 3, 5]
        """
        if days_list is None:
            days_list = [1, 3, 5]

        if institutional_all_df is None or len(institutional_all_df) == 0:
            return {"error": "無法人資料"}

        sector_map = self._build_sector_map()
        df = institutional_all_df.copy()

        # 計算各股淨買賣超
        df["net"] = df["buy"] - df["sell"]

        # 對應族群
        df["sector"] = df["stock_id"].map(sector_map).fillna("其他")

        result = {}
        for days in days_list:
            result[f"{days}d"] = self._calc_rotation(df, days)

        # 資金輪動摘要
        result["summary"] = self._generate_summary(result, days_list)

        return result

    def _calc_rotation(self, df: pd.DataFrame, days: int) -> dict:
        """計算 N 日族群資金流向"""
        dates = sorted(df["date"].unique())

        if len(dates) < days:
            return {"error": f"資料不足 {days} 天"}

        recent_dates = dates[-days:]
        recent = df[df["date"].isin(recent_dates)]

        # 按族群彙總
        sector_flow = recent.groupby("sector")["net"].sum().sort_values(ascending=False)

        # Top 流入 / Top 流出
        top_inflow = sector_flow[sector_flow > 0].head(5).to_dict()
        top_outflow = sector_flow[sector_flow < 0].tail(5).to_dict()

        return {
            "days": days,
            "dates": [str(d.date()) if hasattr(d, "date") else str(d) for d in recent_dates],
            "sector_flow": sector_flow.to_dict(),
            "top_inflow": {k: int(v) for k, v in top_inflow.items()},
            "top_outflow": {k: int(v) for k, v in top_outflow.items()},
            "total_net": int(sector_flow.sum()),
        }

    def _generate_summary(self, result: dict, days_list: list) -> dict:
        """產出資金輪動摘要"""
        summaries = []

        for days in days_list:
            key = f"{days}d"
            data = result.get(key, {})
            if "error" in data:
                continue

            inflow = data.get("top_inflow", {})
            outflow = data.get("top_outflow", {})

            inflow_str = ", ".join(
                [f"{k}(+{v:,})" for k, v in sorted(inflow.items(), key=lambda x: -x[1])[:3]]
            )
            outflow_str = ", ".join(
                [f"{k}({v:,})" for k, v in sorted(outflow.items(), key=lambda x: x[1])[:3]]
            )

            summaries.append({
                "period": f"{days}日",
                "inflow": inflow_str or "無明顯流入",
                "outflow": outflow_str or "無明顯流出",
            })

        # 判斷輪動方向
        rotation_direction = ""
        d3 = result.get("3d", {})
        d5 = result.get("5d", {})

        if d3 and d5 and "error" not in d3 and "error" not in d5:
            inflow_3d = set(d3.get("top_inflow", {}).keys())
            inflow_5d = set(d5.get("top_inflow", {}).keys())
            outflow_3d = set(d3.get("top_outflow", {}).keys())
            outflow_5d = set(d5.get("top_outflow", {}).keys())

            # 持續流入的族群
            consistent_in = inflow_3d & inflow_5d
            consistent_out = outflow_3d & outflow_5d

            if consistent_in and consistent_out:
                rotation_direction = (
                    f"資金持續由 {','.join(consistent_out)} → {','.join(consistent_in)}"
                )
            elif consistent_in:
                rotation_direction = f"資金持續流入 {','.join(consistent_in)}"
            elif consistent_out:
                rotation_direction = f"資金持續流出 {','.join(consistent_out)}"

        return {
            "details": summaries,
            "rotation": rotation_direction or "無明顯輪動趨勢",
        }
