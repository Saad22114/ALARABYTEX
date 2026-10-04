"""دقّةُ المبلغ: كيف يخرج إلى الشبكة، لا كيف يُخزَّن.

في القاعدة كلُّ مبلغ `Decimal` بخانتين. لكنّ ما يُقارَن به لا يُخزَّن:
متوسطُ تكلفة الياردة ناتجُ قسمةٍ لا تنتهي، فمضاعفته في يارداتٍ تعطي
`Decimal` بمئتينٍ وثمانيةٍ وعشرين خانةً معتمدة. و`float` على `Decimal` لا
يقرِّب إلى خانتين، بل يقف عند أقربِ عددٍ ثنائيّ فيمتدُّ الذيل.

فالتقريبُ هنا يقطعه عند منبعه، مرّةً واحدة، قبل أن يخرج إلى الشبكة.
"""

from decimal import Decimal

ZERO = Decimal("0")
MONEY = Decimal("0.01")
RATE = Decimal("0.001")
PERCENT = Decimal("0.1")


def q2(value):
    """`Decimal` بمُرمزين عشريين، لمن يريد البقاءَ في `Decimal`."""
    return Decimal(str(value if value is not None else 0)).quantize(MONEY)


def money(value):
    """مبلغٌ بمُرمزين عشريين، ويبقى في الاستجابة رقماً لا نصاً.

    `float(q2(...))` لا `q2(...)` وحدها: حقل JSON لوحّدُ النوع، فمن كتب
    الحقلَ `Decimal` أخرجه المُرمِّزُ نصاً، فقارَنه العميلُ نصاً برقمٍ.
    """
    return float(q2(value))


def unit_price(value):
    """سعرُ الياردة إلى ثلاث خانات، لأنّه سعرٌ لا مبلغ."""
    return float(Decimal(str(value if value is not None else 0)).quantize(RATE))


def percent(part, whole):
    """نسبةٌ مئوية إلى خانةٍ واحدة، آمنةٌ من القسمة على صفر.

    القسمةُ في `Decimal` لا تنتهي، فواحدٌ على ثلاثة يعطي
    `33.33333333333333333333333333`، و`float` منها يقف عند أقربِ عددٍ ثنائيّ
    فيخرج `33.333333333333336` إلى شارةِ هامشِ الربح. خانةٌ واحدة تكفي،
    فالهامشُ يُقرأ لا يُقاس.
    """
    if not whole:
        return 0.0
    return float(
        (Decimal(str(part)) / Decimal(str(whole)) * 100).quantize(PERCENT)
    )