from typing import List, Tuple
from voltrail_core.models import TripPlan, RiskLevel, Warning

class RiskEngine:
    """
    Đánh giá mức độ rủi ro của TripPlan.
    Trả về (RiskLevel, List[Warning]) thay vì mutate frozen TripPlan.
    """

    @staticmethod
    def evaluate(plan: TripPlan) -> Tuple[RiskLevel, List[Warning]]:
        """
        Trả về mức rủi ro và danh sách cảnh báo mới phát sinh.
        Không mutate plan gốc.
        """
        new_warnings: List[Warning] = []
        lowest_soc = 1.0

        for stop in plan.stops:
            if stop.arrival_soc.p50 < lowest_soc:
                lowest_soc = stop.arrival_soc.p50

            if stop.arrival_soc.p10 < 0.05:
                new_warnings.append(Warning(
                    code="CRITICAL_SOC",
                    message="Rủi ro cao: Trường hợp xấu nhất (p10), pin có thể dưới 5% khi đến trạm sạc.",
                ))

        # Gộp cảnh báo từ plan gốc (ví dụ RestRules) để xét toàn bộ
        all_warnings = list(plan.warnings) + new_warnings

        if any(w.code == "CRITICAL_SOC" for w in all_warnings):
            return RiskLevel.CRITICAL, new_warnings

        if any(w.code == "REST_VIOLATION" for w in all_warnings):
            return RiskLevel.REST_RECOMMENDED, new_warnings

        if lowest_soc < 0.15:
            return RiskLevel.AWARE, new_warnings

        return RiskLevel.SAFE, new_warnings
