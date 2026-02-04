import streamlit as st
import pandas as pd
from docxtpl import DocxTemplate
from io import BytesIO
from datetime import datetime
import os
import json

# ==========================================
# 1. 页面配置
# ==========================================
st.set_page_config(page_title="激光器维修系统 (局域网共享版)", page_icon="🔋", layout="wide")
# ==========================================
# 2. 数据持久化设置 (同级目录版)
# ==========================================
# 获取当前代码所在的文件夹路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据存到代码同级目录的 data 文件夹里
DATA_FOLDER = os.path.join(CURRENT_DIR, "Laser_App_Data")
DB_FILE = os.path.join(DATA_FOLDER, "laser_database.json")

# 【重点】模板直接去读代码旁边的文件，或者也放在 Data 文件夹里
# 方案 A：模板就在代码旁边 (推荐)
TEMPLATE_FILE = os.path.join(CURRENT_DIR, "template.docx") 

def ensure_data_folder_exists():
    """确保文件夹存在"""
    if not os.path.exists(DATA_FOLDER):
        try:
            os.makedirs(DATA_FOLDER)
        except Exception as e:
            st.error(f"❌ 无法创建文件夹 {DATA_FOLDER}，请检查权限。错误: {e}")

def load_data():
    """启动时读取数据"""
    ensure_data_folder_exists()
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_data_to_disk():
    """写入硬盘"""
    ensure_data_folder_exists()
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(st.session_state['db'], f, ensure_ascii=False, indent=4)

# 初始化数据库
if 'db' not in st.session_state:
    st.session_state['db'] = load_data()

# 初始化管理员状态
if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False

# ==========================================
# 3. 初始化表格数据源 (用于清空和默认值)
# ==========================================
def init_dataframes():
    # 1. 基础信息表
    if 'df_basic' not in st.session_state:
        st.session_state.df_basic = pd.DataFrame([{"序列号": "", "型号": "WYP-", "电压": "24V", "操作员": "Guest"}])
    # 2. 外观检查表
    if 'df_inspect' not in st.session_state:
        st.session_state.df_inspect = pd.DataFrame([{"外壳/包装": "完好 Normal", "机械损伤": "无 None"}])
    # 3. 电子参数表
    if 'df_elec' not in st.session_state:
        st.session_state.df_elec = pd.DataFrame([{"工作时长": "", "报警状态": "No Alarm"}])
    # 4. TEC 参数表 (2行)
    if 'df_tec' not in st.session_state:
        st.session_state.df_tec = pd.DataFrame([
            {"名称": "TEC 1", "设定值": "", "回读值": "", "电流": ""},
            {"名称": "TEC 2", "设定值": "", "回读值": "", "电流": ""}
        ])
    # 5. 驱动参数表
    if 'df_driver' not in st.session_state:
        st.session_state.df_driver = pd.DataFrame([{"高压 (HV)": "", "峰值电流": "", "脉宽": ""}])
    # 6. 功率测量表 (动态)
    if 'df_power' not in st.session_state:
        st.session_state.df_power = pd.DataFrame([{"电流 I [A]": "", "脉宽 [us]": "", "波长 λ": "", "功率 P [W]": ""}])
    # 7. 输出功率表
    if 'df_output' not in st.session_state:
        st.session_state.df_output = pd.DataFrame([{"355nm": "", "532nm": "", "1064nm": ""}])
    # 8. 详细维修步骤 (动态)
    if 'df_action' not in st.session_state:
        st.session_state.df_action = pd.DataFrame([{"维修措施": "", "操作员": "Guest", "日期": datetime.now().strftime("%Y-%m-%d")}])

    # 文本域状态
    if 'txt_problem' not in st.session_state: st.session_state.txt_problem = ""
    if 'txt_summary' not in st.session_state: st.session_state.txt_summary = ""
    if 'txt_note' not in st.session_state: st.session_state.txt_note = ""

def reset_all_data():
    """重置所有输入表格"""
    del st.session_state.df_basic
    del st.session_state.df_inspect
    del st.session_state.df_elec
    del st.session_state.df_tec
    del st.session_state.df_driver
    del st.session_state.df_power
    del st.session_state.df_output
    del st.session_state.df_action
    st.session_state.txt_problem = ""
    st.session_state.txt_summary = ""
    st.session_state.txt_note = ""
    init_dataframes()

# 运行初始化
init_dataframes()

# ==========================================
# 4. 文档生成逻辑
# ==========================================
def flatten_data_for_template(record):
    context = record.copy()
    
    # 拍平功率表
    for i, row in enumerate(record.get('power_table', [])):
        suffix = f"_{i+1}"
        context[f"current{suffix}"] = row.get("电流 I [A]", "")
        context[f"pulse{suffix}"] = row.get("脉宽 [us]", "")
        context[f"nm{suffix}"] = row.get("波长 λ", "")
        context[f"power{suffix}"] = row.get("功率 P [W]", "")
    
    # 拍平输出功率
    for i, row in enumerate(record.get('output_table', [])):
        suffix = f"_{i+1}"
        context[f"power_355{suffix}"] = row.get("355nm", "")
        context[f"power_532{suffix}"] = row.get("532nm", "")
        context[f"power_1064{suffix}"] = row.get("1064nm", "")

    # 拍平维修步骤
    for i, row in enumerate(record.get('action_table', [])):
        suffix = f"_{i+1}"
        context[f"action{suffix}"] = row.get("维修措施", "")
        context[f"operator{suffix}"] = row.get("操作员", "")
        context[f"date{suffix}"] = row.get("日期", "")
    return context

def generate_doc(record):
    if not os.path.exists(TEMPLATE_FILE):
        st.error(f"⚠️ 在 {DATA_FOLDER} 中找不到模板文件 template.docx")
        return None
    doc = DocxTemplate(TEMPLATE_FILE)
    final_context = flatten_data_for_template(record)
    try:
        doc.render(final_context)
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer
    except Exception as e:
        return None

# ==========================================
# 5. 侧边栏：管理员
# ==========================================
with st.sidebar:
    st.header("🔧 系统菜单")
    with st.expander("👮‍♂️ 管理员登录"):
        if not st.session_state['is_admin']:
            adm_user = st.text_input("账号")
            adm_pwd = st.text_input("密码", type="password")
            if st.button("登录"):
                if adm_user == "admin" and adm_pwd == "admin":
                    st.session_state['is_admin'] = True
                    st.rerun()
                else:
                    st.error("账号或密码错误")
        else:
            st.success("已登录为管理员")
            if st.button("退出管理员"):
                st.session_state['is_admin'] = False
                st.rerun()

# ==========================================
# 6. 主界面
# ==========================================
st.title("🔋 激光器维修档案系统")
st.caption(f"数据存储位置：{DB_FILE}")

tab1, tab2 = st.tabs(["📝 录入工单", "🔍 历史档案"])

with tab1:
    # 1. 基础信息区
    st.subheader("1. 基础信息 & 外观")
    col1, col2 = st.columns([1.5, 1])
    with col1:
        st.caption("基础参数")
        basic_df = st.data_editor(st.session_state.df_basic, num_rows="fixed", use_container_width=True, hide_index=True, key="ed_basic")
    with col2:
        st.caption("外观检查")
        inspect_df = st.data_editor(st.session_state.df_inspect, num_rows="fixed", use_container_width=True, hide_index=True, key="ed_inspect")

    # 2. 电子参数区
    st.subheader("2. 电子参数 & TEC")
    elec_df = st.data_editor(st.session_state.df_elec, num_rows="fixed", use_container_width=True, hide_index=True, key="ed_elec")
    
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.caption("TEC 参数")
        tec_df = st.data_editor(st.session_state.df_tec, num_rows="fixed", use_container_width=True, hide_index=True, key="ed_tec")
    with c2:
        st.caption("驱动参数")
        driver_df = st.data_editor(st.session_state.df_driver, num_rows="fixed", use_container_width=True, hide_index=True, key="ed_driver")

    # 3. 功率测量
    st.subheader("3. 功率测量")
    power_df = st.data_editor(st.session_state.df_power, num_rows="dynamic", use_container_width=True, key="ed_power")
    
    st.caption("输出功率")
    output_df = st.data_editor(st.session_state.df_output, num_rows="fixed", use_container_width=True, hide_index=True, key="ed_output")

    # 4. 故障描述
    st.subheader("4. 故障与措施")
    problem = st.text_area("故障描述", value=st.session_state.txt_problem, height=100, key="area_problem")
    action_sum = st.text_area("采取措施 (总体描述)", value=st.session_state.txt_summary, height=100, key="area_summary")
    
    st.caption("详细维修步骤")
    action_df = st.data_editor(st.session_state.df_action, num_rows="dynamic", use_container_width=True, hide_index=True, key="ed_action")
    
    note = st.text_area("备注", value=st.session_state.txt_note, height=68, key="area_note")

    st.markdown("---")
    
    if st.button("💾 保存并写入硬盘", type="primary"):
        try:
            sn_val = basic_df.iloc[0]["序列号"]
            if not sn_val:
                st.error("❌ 保存失败：序列号不能为空！")
            else:
                # 提取数据
                record = {
                    "id": len(st.session_state['db']) + 1,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "sn": sn_val,
                    "model": basic_df.iloc[0]["型号"], "voltage": basic_df.iloc[0]["电压"], "operator": basic_df.iloc[0]["操作员"],
                    "obs_case": inspect_df.iloc[0]["外壳/包装"], "obs_mech": inspect_df.iloc[0]["机械损伤"],
                    "work_hours": elec_df.iloc[0]["工作时长"], "alarms": elec_df.iloc[0]["报警状态"],
                    "hv": driver_df.iloc[0]["高压 (HV)"], "current": driver_df.iloc[0]["峰值电流"], "pulse": driver_df.iloc[0]["脉宽"],
                    "tec1_set": tec_df.iloc[0]["设定值"], "tec1_read": tec_df.iloc[0]["回读值"], "tec1_peltier": tec_df.iloc[0]["电流"],
                    "tec2_set": tec_df.iloc[1]["设定值"], "tec2_read": tec_df.iloc[1]["回读值"], "tec2_peltier": tec_df.iloc[1]["电流"],
                    "problem": problem, "action": action_sum, "note": note,
                    "power_table": power_df.to_dict('records'),
                    "output_table": output_df.to_dict('records'),
                    "action_table": action_df.to_dict('records')
                }
                
                # 存入内存
                st.session_state['db'].append(record)
                
                # 写入硬盘
                save_data_to_disk()
                
                st.success(f"✅ 序列号 {sn_val} 已保存到 D:\Laser_App_Data！")
                reset_all_data()
                st.rerun()
                
        except Exception as e:
            st.error(f"数据提取或保存错误: {e}")

# --- TAB 2: 历史记录 ---
with tab2:
    st.header("🗄️ 维修档案库")
    search_term = st.text_input("🔍 搜索序列号:")
    
    display_data = st.session_state['db']
    if search_term:
        display_data = [d for d in display_data if search_term.lower() in d['sn'].lower()]

    if not display_data:
        st.info("暂无数据。")
    else:
        for i, record in enumerate(reversed(display_data)):
            with st.expander(f"📅 {record['date']} | SN: {record['sn']} | {record['operator']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**故障:** {record['problem']}")
                    st.write(f"**措施:** {record['action']}")
                with col2:
                    doc_file = generate_doc(record)
                    if doc_file:
                        st.download_button("📥 下载 Word", doc_file, f"Report_{record['sn']}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_{record['id']}")
                    else:
                        st.warning("⚠️ 模板文件 template.docx 不存在")
                    
                    if st.session_state['is_admin']:
                        if st.button("🗑️ 删除并同步", key=f"del_{record['id']}"):
                            st.session_state['db'] = [d for d in st.session_state['db'] if d['id'] != record['id']]
                            save_data_to_disk()
                            st.rerun()
