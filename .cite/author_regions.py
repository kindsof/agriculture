#!/usr/bin/env python3
"""Attach folk_detail / civilization dossiers to the remaining 8 farming regions.

Sources are never invented here: every citation is either an in-repo text
(`/read.html?id=…`, title taken from books/catalog.json) or the already verified
source of an existing site in sites.yaml (looked up by id).  An entry whose
sources all fail to resolve is dropped and reported, never shipped with a
placeholder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGIONS = ROOT / "web" / "data" / "regions_source.json"
SITES = ROOT / "web" / "data" / "sites.yaml"
CATALOG = ROOT / "books" / "books" / "catalog.json"


def load_catalog():
    for path in (ROOT / "books" / "catalog.json", CATALOG):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            works = data["works"] if isinstance(data, dict) else data
            return {w["id"]: w for w in works}
    return {}


CATALOG_BOOKS = load_catalog()
SITES_DB = {s["id"]: s for s in yaml.safe_load(
    SITES.read_text(encoding="utf-8"))["sites"]}


def B(book_id: str) -> dict | None:
    """Cite a book we actually hold."""
    work = CATALOG_BOOKS.get(book_id)
    if not work:
        return None
    author = work.get("author") or ""
    who = f"（{work.get('dynasty', '')}）{author}".rstrip()
    return {
        "title": f"《{work['title']}》{who}·本站馆藏全文",
        "url": f"/read.html?id={book_id}",
    }


def S(site_id: str) -> dict | None:
    """Reuse a site's already-verified source."""
    site = SITES_DB.get(site_id)
    if not site or not site.get("sources"):
        return None
    first = site["sources"][0]
    return {"title": first["title"], "url": first["url"]}


def F(*cits):
    return [c for c in cits if c]


DOSSIER = {
    "dongbei": {
        "folk_detail": [
            ("岁时节令", "立春鞭春牛、二月二引龙添仓、五月端午采艾、六月六祭虫王、秋收后谢土；腊月廿三祭灶之后即入『猫冬』，上油修犁、编绳纳网，农事作息由长冬切分为两段。",
             F(B("KR2j0001"), B("NX0020"))),
            ("祭祀信仰", "满族有堂子祭与柳条祭祀，朝鲜族以农乐舞祭天祈丰，山区奉山神、树神与『胡黄白柳灰』五家，田头插红布、田边留『免耕一角』以示让给兽类。",
             F(B("KR2j0002"), S("custom-nadamu"))),
            ("饮食物俗", "杀猪菜、酸菜白肉、粘豆包、冻梨冻秋梨与乌拉满族火锅，皆是长冬储食技术的产物；朝鲜族打糕、冷面随稻作传入，秋菜入窖、冻货埋雪可存至开春。",
             F(B("NX0008"), B("KR2j0002"))),
            ("技艺工坊", "垄作是本区核心技术：扣种、搅垄、大垄三茬以御低温涝渍；耲耬点播、拉秋打场、火炕泥墙；今日以深松整地与秸秆覆盖对抗黑土板结。",
             F(B("KR3d0005"), B("NX0010"))),
            ("农谚俗信", "无霜期不足百日，农谚皆以节令为纲：『立春一年端，种地早盘算』『处暑高粱白露谷』；误种数日常致一年无收，故节令禁忌之严为各省最。",
             F(B("KR3d0010"), B("NX0020"))),
        ],
        "civilization": [
            ("起源遗存", "本区稻作晚起而成就卓著：渤海国『卢城之稻』已见唐籍，清代宁安响水稻、桓仁京租稻皆为贡米；粟作则沿辽西与燕山北缘传入，与农牧交错带的敖汉八千年粟作同出一源。",
             F(S("ningan-rice"), S("huanren-rice"), S("civilization-xinglonggou"))),
            ("农书典籍", "《农桑辑要》为元代司农司官修，主体是北方旱地农桑技术；《钦定授时通考》汇历代农政与节令；《马首农言》记山西寿阳旱作，可为本区旱农参照。",
             F(B("KR3d0003"), B("KR3d0010"), B("NX0037"))),
            ("制度田制", "清代柳条边封禁至光绪开禁，『闯关东』移民以领照拓荒、永佃租种取得耕地；此后满铁附属地、集体化与国营农场先后塑造了今日全国规模最大、机械化程度最高的经营格局。",
             F(B("KR3d0010"), B("KR2m0048"))),
            ("科技成就", "玉米大垄双行、膜下滴灌与寒地水稻旱育稀植把『无霜期短』的约束压到最低；保护性耕作（秸秆覆盖、免耕少耕）在黑土区大面积推广，商品粮率居全国之首。",
             F(B("KR3d0005"), S("ningan-rice"))),
        ],
    },
    "huabei": {
        "folk_detail": [
            ("岁时节令", "正月填仓、二月二引龙、清明禁火插柳、五月端午、六月六晒种晒衣、七月十五以新麦荐祖、十月一送寒衣、冬至数九；麦收前祭仓神，收毕演剧『谢仓』。",
             F(B("KR2j0001"), B("NX0020"))),
            ("祭祀信仰", "后土、社公、仓王、马王牛王与龙王并祀，大旱则打旱魃、抬龙王求雨；先农坛的国家级耤田礼与本区的民间祈谷实为一套秩序的两端。",
             F(B("KR2j0002"), S("civilization-xiannongtan"))),
            ("饮食物俗", "以麦食为骨：馒头、煎饼、烙饼、水饺与玉米豆面窝头；花馍用于婚丧祭祀，枣、柿、栗入冬为常食；《齐民要术》所记酱、酢、脯、鲊的北方食制至今仍在其脉。",
             F(B("KR3d0001"), B("KR2j0002"))),
            ("技艺工坊", "耕—耙—耱的保墒链条、区田区种、三脚耧车播种、石磨石碾加工、井灌辘轳与龙骨水车、棉田摘心打顶，构成华北旱作的完整技艺系统。",
             F(B("NX0014"), B("KR3d0005"))),
            ("农谚俗信", "二十四节气在黄河流域定型，本区谚语最密：『白露早、寒露迟，秋分种麦正当时』『清明前后，栽瓜种豆』『麦要胎生水』；谚到今天仍是播种的实际依据。",
             F(B("KR3d0010"), S("dengfeng-solar-terms"))),
        ],
        "civilization": [
            ("起源遗存", "武安磁山的窖穴囤粟、新郑裴李岗的石磨盘石磨棒把黄河中游粟作推到八千年前后；舞阳贾湖稻粟兼作；安阳殷墟甲骨卜辞中的『求年』『协田』，是中国最早成文的农业档案。",
             F(S("civilization-cishan"), S("civilization-peiligang"), S("civilization-yinxu"))),
            ("农书典籍", "从汉代《氾胜之书》的区田与溲种、北魏《齐民要术》的耕耙耱法，到元代《农桑辑要》与清代《授时通考》的官修集成，黄河流域始终是中国农书最密集之地。",
             F(B("NX0014"), B("KR3d0001"), B("KR3d0003"))),
            ("制度田制", "汉代代田、区田，曹魏屯田，北魏均田与唐代租庸调皆先在华北试行；元代以五十家为『社』劝课农桑，明代设粮长催科，田制与赋役在此地反复试验后再推行天下。",
             F(B("KR3d0003"), B("KR2m0048"))),
            ("科技成就", "耧车、翻车、筒车与旋转石磨先后在此定型；保墒覆盖与豆麦轮作使黄土旱地连续耕种两千年而地力不衰；今日冬小麦—夏玉米一年两熟与节水灌溉，支撑全国最大的麦区。",
             F(B("NX0010"), S("civilization-dawenkou"))),
        ],
    },
    "huangtu": {
        "folk_detail": [
            ("岁时节令", "正月二十补天节与填仓、清明插柳、端午系长命缕、六月六祭土地、秋后赛社酬神、腊月祭灶与蒸年馍；窑洞院落中的年馍花样按辈分分发，序列分明。",
             F(B("KR2j0001"), B("KR2j0002"))),
            ("祭祀信仰", "汾阴后土祠国家祭地与村社赛愿相接，祈雨则抬龙王、打龙坑；马王庙、牛王庙与场院神位俱全，窑洞门窗压镇物以避五毒。",
             F(B("KR2j0002"), S("custom-huangdimiao"), S("custom-shehuo"))),
            ("饮食物俗", "小米粥养人、莜面栲栳栳、饸饹与羊汤泡馍为日常；枣馍与花馍专供祭祀婚丧，柿饼、核桃与红枣入窖过冬，皆是少雨干旱下的储能食俗。",
             F(B("KR3d0001"), B("NX0037"))),
            ("技艺工坊", "区田集中用水、梯田垒石堰、场院碌碡碾场、窑洞冬暖夏凉近乎零能耗；晋中大院的粮窖与商路，把旱地余粮换成可流通的资本。",
             F(B("NX0014"), B("NX0037"))),
            ("农谚俗信", "『收麦如救火』『麦收三道手』写尽抢收之急；祈雨期间忌晒衣、忌动土；信天游里的农事歌谣把节气、墒情与作物写成可调的句子。",
             F(B("NX0037"), B("KR3d0010"))),
        ],
        "civilization": [
            ("起源遗存", "秦安大地湾的黍粟、西安半坡的窖粟、神木石峁的石城与神树祠、襄汾陶寺以十七道缝观日定节的观象台，串起黄土高原从旱作起源到农时历法的完整链条。",
             F(S("civilization-taosi"), S("civilization-shimao"), S("civilization-banpo"), S("civilization-dadiwan"))),
            ("农书典籍", "汉代《氾胜之书》出于三辅农区，其区田法专为旱地而设；清代《马首农言》逐月记山西寿阳的耕、种、收、藏，是黄土高原旱作最具体的近代农书。",
             F(B("NX0037"), B("NX0014"))),
            ("制度田制", "周籍田与私田之变、秦『废井田、开阡陌』、汉代移民实边与河西屯田，皆发生或由此推广；清代晋商垦地与粮庄经营，把黄土高原的旱粮纳入长途贸易。",
             F(B("KR3d0010"), S("custom-shehuo"))),
            ("科技成就", "区田与代田以局部集水应对干旱，淤地坝与梯田把沟壑变成耕地；今日全膜覆盖与集雨补灌延续的仍是同一思路——在同质干旱中制造局部的水分优势。",
             F(B("NX0014"), S("civilization-taosi"))),
        ],
    },
    "huanan": {
        "folk_detail": [
            ("岁时节令", "二月初二土地诞与『开耕节』、『洗犁节』拉开一年农事，清明祭祖并修陂塘，端午龙舟，六月六晒谱，冬至『亚岁』大如年；双季稻使节令体系一年两转。",
             F(B("KR2j0002"), S("custom-mazu"))),
            ("祭祀信仰", "妈祖、土地、社公与蔗神、茶仙同祀；壮族蚂拐节以祭蛙祈子祈丰，疍家水上人家祀龙母，客家园围中设祖堂兼祀山神。",
             F(S("donglan-frog-festival"), S("custom-mazu"))),
            ("饮食物俗", "新米尝新先荐祖先，糯食与五色饭用于节令；凉茶与老火汤应对暑湿，潮汕工夫茶成礼俗，荔枝龙眼制干、甘蔗制片糖是岭南的冬储方式。",
             F(B("NX0024"), S("fuzhou-jasmine"))),
            ("技艺工坊", "桑基、蔗基鱼塘以塘泥壅基、基上 Feed 桑蔗循环；荔枝高空压条与嫁接、糖寮榨蔗、蓑衣与龙骨水车，构成水热丰沛之地的精巧技艺。",
             F(B("NX0010"), S("foshan-dike-pond"))),
            ("农谚俗信", "『未食五月粽，寒衣未入冧』以食俗标寒意；布谷催耕、蚁搬家与海沙云起皆主风雨，占候之学随《田家五行》一路南传，与本地台风经验合流。",
             F(B("NX0019"), B("KR2j0002"))),
        ],
        "civilization": [
            ("起源遗存", "万年仙人洞与吊桶环出土一万年前后的陶片与稻作植硅体，是世界农业起源的关键坐标；隆安『那』文化稻作系统与琼中山兰稻，则记录稻作在岭南与海南的多支路径。",
             F(S("wannian-rice"), S("longan-na-culture"), S("qiongzhong-shanlan"))),
            ("农书典籍", "《养鱼经》是最早的淡水养殖经营文献；《糖霜谱》专记甘蔗与结糖之法；《农政全书》收岭南作物与荒政之议，三者合成本区最早的农学文本群。",
             F(B("NX0002"), B("NX0024"), B("KR3d0007"))),
            ("制度田制", "宋代占城稻自福建推广至江淮，改写全国稻作格局；明清沙田围垦与田赋折银、侨乡『公尝田』族产经营，形成国家税则之外的地方田土秩序。",
             F(B("KR3d0007"), B("KR2m0049"))),
            ("科技成就", "占城稻的早熟耐旱引入、基塘物质循环、双季稻与再生稻、荔枝低温贮藏与嫁接，皆是对高温高湿环境的正面回应；今日杂交稻与荔枝冷藏更把这一传统推向全国。",
             F(B("NX0010"), S("fuzhou-jasmine"))),
        ],
    },
    "xinan": {
        "folk_detail": [
            ("岁时节令", "傣历泼水节与稻作新年同步，开秧门、火把节、冬祭山神依次而行；彝族十月太阳历把一年分为寒热二季，节期直接与农事相位对应。",
             F(S("custom-huobajie"), S("custom-guzhang"))),
            ("祭祀信仰", "祭山神、祭龙树、梯田『祭水口』，侗寨祭萨与鼓楼议事并行；哈尼寨神林禁伐禁牧，实为水源林的信仰化保护。",
             F(S("congjiang-rice-fish-duck"), S("custom-sanyuejie"))),
            ("饮食物俗", "哈尼长街宴以梯田鱼、糯食与红米待客，黔东南酸汤与糯米养出『酸食』一系，川渝的辣椒与花椒、普洱的紧压茶各有其山地保存逻辑。",
             F(S("hani-terrace"), S("congjiang-rice-fish-duck"))),
            ("技艺工坊", "哈尼梯田以木刻『刻木量水』分水到户，竹笕跨山引水；稻鱼鸭共作一田三利；织锦、沤麻与普洱茶压制皆在农闲完成。",
             F(S("hani-terrace"), B("NX0010"))),
            ("农谚俗信", "梯田社会最重水规：『木刻分水』『水到田头不论辈』；火把节绕田驱虫、荞禳蝗灾，把病虫防治写成可执行的仪式。",
             F(S("custom-huobajie"), B("KR2m0047"))),
        ],
        "civilization": [
            ("起源遗存", "稻作在西南并非单一起源：傣族旱稻、侗族糯禾的长期保种、云贵高原的野生稻与驯化稻并存，构成世界上罕见的『稻作基因库』式分布。",
             F(S("congjiang-rice-fish-duck"), S("custom-buluotuo"))),
            ("农书典籍", "《农桑辑要》记蜀中桑麻之利，《天工开物》载川黔的井盐、蔗作与竹器，《农政全书》收西南作物与荒政，皆可补中原农书对山地农业的失载。",
             F(B("KR3d0003"), B("NX0010"))),
            ("制度田制", "都江堰设『水则』与岁修之制，官堰灌溉有册有令；明清改土归流后屯垦与苗疆田赋并进，土司份地之上再叠今天的承包到户，山地地权层层相因。",
             F(S("dujiangyan"), B("KR3d0010"))),
            ("科技成就", "都江堰『深淘滩、低作堰』两千年不废；梯田木刻分水即原始的量水配水制度；稻鱼鸭共生被认定为全球重要农业文化遗产，普洱古茶树的选育与后发酵则是山地的生物技术。",
             F(S("dujiangyan"), S("hani-terrace"))),
        ],
    },
    "xibei": {
        "folk_detail": [
            ("岁时节令", "春社开渠、清明放水、六月六祭渠神，麦收后谢天；哈萨克族纳吾鲁孜于春分辞旧迎新、恰在转场与春播之间；中秋分瓜、冬宰储物，多历并行而不相乱。",
             F(B("KR2j0002"), S("turpan-karez"), S("custom-nawuruz"))),
            ("祭祀信仰", "渠神、龙王与山神并祀，花儿会亦含赛愿还愿；扎尕那以山神禁伐护林，坎儿井掏捞夫有行规与禁忌，水比土贵之地的信仰皆围绕水。",
             F(S("zhagana"), S("custom-huaerhua"))),
            ("饮食物俗", "面食为纲：拉条、馕、馓子与焜锅馍；手抓羊肉与奶茶是牧农共食；枸杞、瓜干、红枣入冬为常储，盖碗茶则待客议事。",
             F(S("ningxia-yellow-river"), S("hami-melon"))),
            ("技艺工坊", "坎儿井以竖井定线、暗渠截潜流，掏捞全凭人力；葡萄晾房以干热风阴干制干；棉田整枝打顶、枸杞晒场与滩田引黄石闸，皆与极旱气候博弈。",
             F(S("turpan-karez"), S("hami-melon"))),
            ("农谚俗信", "雪水按渠册轮灌的『水令』最严，私开水口受罚；麦收忌大风，晒场忌坐碌碡；祁连雪线与葡萄出土的物候即播种移栽的历书。",
             F(S("ningxia-yellow-river"), B("KR2k0078"))),
        ],
        "civilization": [
            ("起源遗存", "秦安大地湾的黍粟、吉木乃通天洞里距今两千五百年前后的炭化小麦与黍、甘南扎尕那的农林牧复合系统，同处一条作物自东西双向涌入的通道之上。",
             F(S("civilization-tongtiandong"), S("civilization-dadiwan"), S("zhagana"), B("KR1b0008"))),
            ("农书典籍", "《水经注》与《行水金鑑》存西北水道与河政之详，《农桑辑要》论棉、《木棉谱》记棉花治理、《农政全书》收西北作物，构成旱区农学的文本基础。",
             F(B("KR2k0058"), B("NX0012"), B("KR3d0007"))),
            ("制度田制", "汉代河西屯田与亭障、唐代设渠堰之官、清代引黄渠册与『水价』征收，皆以水权而非田亩为管理核心；今日新疆团场与灌区农民用水者协会是这一传统的延伸。",
             F(S("ningxia-yellow-river"), B("KR2k0078"))),
            ("科技成就", "坎儿井以地下暗渠避蒸发，与地面渠道相比省水过半；宁夏引黄古灌区无坝引水沿用两千余年、列入世界灌溉工程遗产；今日膜下滴灌使旱作水分利用率再上一阶。",
             F(S("ningxia-yellow-river"), S("turpan-karez"))),
        ],
    },
    "caoyuan": {
        "folk_detail": [
            ("岁时节令", "白节（正月）拜火辞旧，五月六月祭敖包祈丰，七八月那达慕集会议事并验畜，腊月祭火送旧；剪毛、打马鬃、配种、打草各有定月，节令即畜令。",
             F(S("custom-nadamu"), B("KR2j0002"))),
            ("祭祀信仰", "祭敖包、祭火、祭苏鲁锭，敖包既为路标亦为一方水土之主；神山圣湖禁猎禁渔，喇嘛嘛呢祈丰，牧民的信仰边界同时是资源的红线。",
             F(S("custom-nadamu"), S("ar-horqin-nomadic"))),
            ("饮食物俗", "白食（奶食）先于红食（肉食）为敬客之序，熬茶与奶茶终日不辍；炒米、风干肉与奶豆腐是转场干粮，农区则以莜面、荞麦饸饹为主。",
             F(S("ar-horqin-nomadic"), B("KR3d0003"))),
            ("技艺工坊", "四季轮牧与打草储冬是核心技艺，蒙古包营造无钉无绳结、可拆可驮；擀毡、熟皮与套马烙印皆有定法；阴山北麓旱作则以莜麦、马铃薯耐寒。",
             F(S("ar-horqin-nomadic"), B("NX0001"))),
            ("农谚俗信", "草场习惯法重于文字：禁猎期、禁垦坡、忌踏火与忌踩门槛皆有约束力；播种看草芽物候，畜群看膘情定转场时辰。",
             F(S("ar-horqin-nomadic"), B("NX0017"))),
        ],
        "civilization": [
            ("起源遗存", "敖汉兴隆洼与兴隆沟遗址出土八千年前后的炭化黍与粟，是农牧交错带最北、最早的粟作证据；夏家店下层文化的石城与粮窖，说明这里曾有过相当规模的旱作定居。",
             F(S("aohan-dryland"), S("civilization-xinglonggou"))),
            ("农书典籍", "《农桑辑要》并收北方畜牧与桑麻，《养羊法》与《牛羊日历》存畜牧兽医古法，《马首农言》述阴山南麓旱作；牧业在本国农书中从不缺席。",
             F(B("KR3d0003"), B("NX0001"), B("NX0017"))),
            ("制度田制", "盟旗制度划定牧地、按旗纳贡，清末放垦与『蒙地押荒』使农地北推，今日以草畜双承包、禁牧休牧与生态补奖重新给草场减压。",
             F(S("ar-horqin-nomadic"), B("KR2m0048"))),
            ("科技成就", "旱作全膜覆盖与集雨补灌把半干旱区收成稳定下来；青贮玉米与肉牛繁育改变『夏饱秋肥冬瘦春死』的魔咒；遥感监测与休牧轮牧补贴使草畜平衡可核算。",
             F(S("aohan-dryland"), B("NX0010"))),
        ],
    },
    "qingzang": {
        "folk_detail": [
            ("岁时节令", "藏历新年跳神与酥油花启岁，春播开犁祭田，望果节绕田转圈报谢，燃灯节与青海土族纳顿的秋报相接；高原无霜期极短，节令全部围着青稞物候转。",
             F(S("tibetan-wangguo"), S("nadun-festival"))),
            ("祭祀信仰", "山神『拉则』插箭、田头祭田神、神山圣湖禁采禁渔；转山转田的方向与时辰皆有定制，信仰即高原资源管理的执行机制。",
             F(S("tibetan-wangguo"), S("sanjiangyuan-nomadic"))),
            ("饮食物俗", "糌粑与酥油茶为日食，青稞酒与酸奶、奶渣供节庆，湟水谷地的酿皮与焜锅馍自成一路；高寒缺柴，牛粪饼是最主要的燃料与肥料。",
             F(S("nedong-barley"), B("KR3d0003"))),
            ("技艺工坊", "『打阿嘎』以人众轮踏阿嘎土筑屋脊与晒场；木犁配牛、青稞架晾穗；草甸围栏与打草储冬是牧业过冬的关键工序。",
             F(S("nedong-barley"), S("sanjiangyuan-nomadic"))),
            ("农谚俗信", "『春分不及时，谷子空着粒』写尽高原播种之迫；播种择吉日、望果绕田以禳虫灾，田头忌杀生，仪式承担着植保与水土保持的功能。",
             F(S("tibetan-wangguo"), B("KR2j0002"))),
        ],
        "civilization": [
            ("起源遗存", "昌都卡若遗址出土炭化粟与磨制石锄，证明粟作曾沿横断山谷上到高原；青稞的驯化与河谷灌溉在拉萨河、年楚河谷成型，奠定今日高原农业走廊的骨架。",
             F(S("civilization-karyo"), B("NX0010"))),
            ("农书典籍", "《农桑辑要》与《农政全书》述西陲麦类，《救荒本草》与《野菜博录》收高原可食植物；中原农书对青稞与高寒经营的记述虽疏，却是最早的成文线索。",
             F(B("KR3d0006"), B("KR3d0009"))),
            ("制度田制", "吐蕃以来以庄园为单位经营耕地与农户差役，清代沿用谿卡体制；青海蒙藏地区行旗地制。今日耕地承包、草场有偿流转与生态补奖取代了差地制。",
             F(S("nedong-barley"), B("KR2k0072"))),
            ("科技成就", "河谷灌区的木石水闸与常年岁修，耐寒早熟青稞育种，地膜与高原温室让叶菜在海拔四千米落地，草场承包加生态补奖使超载过牧可被量化纠偏。",
             F(S("nedong-barley"), S("sanjiangyuan-nomadic"))),
        ],
    },
}


def main() -> int:
    data = json.loads(REGIONS.read_text(encoding="utf-8"))
    dropped, written = [], 0
    for region in data["regions"]:
        dossier = DOSSIER.get(region["id"])
        if not dossier:
            continue
        for block_name in ("folk_detail", "civilization"):
            items = []
            for kind, text, sources in dossier[block_name]:
                if not sources:
                    dropped.append(f"{region['id']}/{block_name}/{kind}")
                    continue
                items.append({"kind": kind, "text": text, "sources": sources})
                written += 1
            region[block_name] = items
        order = ["id", "name", "color", "provinces", "summary", "crops",
                 "folkways", "folk_detail", "civilization", "heritage_note",
                 "books"]
        ordered = {k: region[k] for k in order if k in region}
        ordered.update({k: v for k, v in region.items() if k not in ordered})
        region.clear()
        region.update(ordered)
    REGIONS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"写入了 {written} 条档案条目")
    if dropped:
        print("来源未解析而被丢弃：")
        for d in dropped:
            print("  - " + d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
