from typing import List
from voltrail_core.models import TripPlan, Warning

class RestRules:
    """
    Quy tắc an toàn khi lái xe:
    - Lái xe liên tục tối đa 4 tiếng -> Phải nghỉ ít nhất 30 phút.
    - Lái xe tổng cộng trong ngày tối đa 10 tiếng -> Phải nghỉ qua đêm.
    """
    MAX_CONTINUOUS_DRIVE_S = 4 * 3600
    MIN_REST_DURATION_S = 30 * 60

    @classmethod
    def apply_rest_rules(cls, plan: TripPlan) -> List[Warning]:
        """
        Kiểm tra nếu có vi phạm quy tắc nghỉ ngơi và trả về danh sách Warning.
        KHÔNG mutate plan gốc (frozen-safe).
        """
        new_warnings: List[Warning] = []
        continuous_drive = 0

        for i, leg in enumerate(plan.legs):
            continuous_drive += leg.duration_s

            if continuous_drive > cls.MAX_CONTINUOUS_DRIVE_S:
                new_warnings.append(Warning(
                    code="REST_VIOLATION",
                    message=f"Chặng {i + 1} vi phạm: Lái xe liên tục quá 4 tiếng không nghỉ.",
                ))

            # Nếu có trạm sạc sau chặng này và nghỉ đủ lâu -> reset đếm
            if i < len(plan.stops):
                stop = plan.stops[i]
                if stop.charge_duration_s >= cls.MIN_REST_DURATION_S:
                    continuous_drive = 0

        return new_warnings
