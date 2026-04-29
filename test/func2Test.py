#!/usr/bin/python
# -*- coding: UTF-8 -*-

#import 别人的文件，默认会先执行
# import funcTest

#只引入一部分，该运行的脚本还是会运行
# from mathTest import prn
#import mathTest

# 导入必要的库用于Excel导出
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("警告: pandas未安装，Excel导出功能将不可用")

# print("funcTest2=======================================")

# print("test")
#mathTest.prn(3)
# prn(31)
#如果先加载 funcTest会触发2的加载，2运行时1还不存在，下列代码会报错
#funcTest.func1()
#print(funcTest.total)



def calculate_accident_responsibility(parties_duration, fixed_duration, use_fixed_algorithm=True):
    """
    计算事故定责比例的算法
    
    参数:
    parties_duration: 字典，格式如 {'A': 10, 'B': 30, 'C': 1}，A是起因方，其他是被影响方
    fixed_duration: 固定时长（分钟）
    use_fixed_algorithm: 是否使用固定算法，True为算法1，False为算法2
    
    返回:
    字典，包含各方的影响时长和责任比例
    """
    if not parties_duration:
        return {}
    
    # 获取起因方（第一个）和被影响方
    parties_list = list(parties_duration.items())
    cause_party, cause_duration = parties_list[0]  # A是起因方
    affected_parties = parties_list[1:]  # B、C等是被影响方
    
    # 计算实际使用的固定时长
    if use_fixed_algorithm:
        # 算法1：使用原始固定时长
        actual_fixed_duration = fixed_duration
    else:
        # 算法2：固定时长/参与方数量
        actual_fixed_duration = fixed_duration / len(parties_duration)
    
    # 存储各方的影响时长
    impact_durations = {}

    # pct = 2/3
    pct = 1/2
    
    # 计算起因方A的影响时长
    a_additional_impact = 0
    for party_name, party_duration in affected_parties:
        if party_duration <= actual_fixed_duration:
            # B持续时间 <= 固定时长：A增加 B时长*2/3
            a_additional_impact += party_duration * pct
        else:
            # B持续时间 > 固定时长：A增加 固定时长*2/3
            a_additional_impact += actual_fixed_duration * pct
    
    impact_durations[cause_party] = cause_duration + a_additional_impact
    
    # 计算被影响方的影响时长
    for party_name, party_duration in affected_parties:
        if party_duration <= actual_fixed_duration:
            # B持续时间 <= 固定时长：B的影响 = B时长*1/3
            impact_durations[party_name] = party_duration * (1-pct)
        else:
            # B持续时间 > 固定时长：B的影响 = 固定时长*1/3 + (B时长-固定时长)
            impact_durations[party_name] = actual_fixed_duration * (1-pct) + (party_duration - actual_fixed_duration)
    
    # 计算总影响时长
    total_impact = sum(impact_durations.values())
    
    # 计算各方责任比例
    responsibility_ratios = {}
    for party, impact in impact_durations.items():
        responsibility_ratios[party] = (impact / total_impact) * 100 if total_impact > 0 else 0
    
    return {
        'original_durations': parties_duration,
        'fixed_duration': actual_fixed_duration,
        'algorithm_type': '固定算法' if use_fixed_algorithm else '非固定算法',
        'impact_durations': impact_durations,
        'total_impact': total_impact,
        'responsibility_ratios': responsibility_ratios
    }


def print_accident_analysis(result):
    """
    格式化输出事故分析结果
    """
    print(f"\n=== 事故定责分析 ({result['algorithm_type']}) ===")
    print(f"原始持续时长: {result['original_durations']}")
    print(f"使用的固定时长: {result['fixed_duration']:.2f} 分钟")
    print(f"总影响时长: {result['total_impact']:.2f} 分钟")
    
    print("\n各方影响时长:")
    for party, impact in result['impact_durations'].items():
        print(f"  {party}: {impact:.2f} 分钟")
    
    print("\n各方责任比例:")
    for party, ratio in result['responsibility_ratios'].items():
        print(f"  {party}: {ratio:.2f}%")


def generate_test_cases():
    """
    生成各种测试案例，包括正常和极端情况
    """
    test_cases = []
    
    # 正常情况测试
    normal_cases = [
        # 2方参与
        {'A': 4, 'B': 14},
        {'A': 25, 'B': 35},
        {'A': 10, 'B': 45},
        
        # 3方参与
        {'A': 10, 'B': 20, 'C': 15},
        {'A': 20, 'B': 25, 'C': 35},
        {'A': 30, 'B': 40, 'C': 10},
        
        # 4方参与
        {'A': 15, 'B': 25, 'C': 20, 'D': 30},
        {'A': 20, 'B': 35, 'C': 15, 'D': 40},
        
        # 5方参与
        {'A': 10, 'B': 20, 'C': 30, 'D': 25, 'E': 35},
    ]
    
    # 极端情况测试
    extreme_cases = [
        # 极短时长
        {'A': 1, 'B': 2},
        {'A': 1, 'B': 2, 'C': 1},
        {'A': 5, 'B': 1, 'C': 1, 'D': 2},
        
        # 极长时长
        {'A': 120, 'B': 180},
        {'A': 200, 'B': 300, 'C': 150},
        {'A': 500, 'B': 600, 'C': 400, 'D': 700},
        
        # 差异极大
        {'A': 1, 'B': 100},
        {'A': 5, 'B': 200, 'C': 1},
        {'A': 10, 'B': 500, 'C': 2, 'D': 300},
        
        # 起因方时长很长
        {'A': 200, 'B': 10, 'C': 15},
        {'A': 300, 'B': 5, 'C': 8, 'D': 12},
        
        # 被影响方都很短
        {'A': 50, 'B': 5, 'C': 3, 'D': 2, 'E': 1},
        
        # 被影响方都很长
        {'A': 10, 'B': 200, 'C': 300, 'D': 250},
        
        # 多方参与，时长各异
        {'A': 25, 'B': 100, 'C': 5, 'D': 200, 'E': 15, 'F': 300},
    ]
    
    # 标记测试类型
    for case in normal_cases:
        test_cases.append(('正常情况', case))
    
    for case in extreme_cases:
        test_cases.append(('极端情况', case))
    
    return test_cases


def analyze_algorithm_performance(test_cases, fixed_duration=30):
    """
    分析两种算法的性能表现
    """
    results = []
    
    for case_type, parties in test_cases:
        # 计算两种算法的结果
        result_fixed = calculate_accident_responsibility(parties, fixed_duration, True)
        result_dynamic = calculate_accident_responsibility(parties, fixed_duration, False)
        
        # 分析结果
        analysis = {
            '测试类型': case_type,
            '参与方数量': len(parties),
            '原始时长': str(parties),
            '固定时长': fixed_duration,
            
            # 算法1结果
            '算法1_实际固定时长': result_fixed['fixed_duration'],
            '算法1_总影响时长': round(result_fixed['total_impact'], 2),
            '算法1_起因方比例': round(list(result_fixed['responsibility_ratios'].values())[0], 2),
            
            # 算法2结果  
            '算法2_实际固定时长': round(result_dynamic['fixed_duration'], 2),
            '算法2_总影响时长': round(result_dynamic['total_impact'], 2),
            '算法2_起因方比例': round(list(result_dynamic['responsibility_ratios'].values())[0], 2),
            
            # 比较分析
            '总影响时长差异': round(abs(result_fixed['total_impact'] - result_dynamic['total_impact']), 2),
            '起因方比例差异': round(abs(list(result_fixed['responsibility_ratios'].values())[0] - 
                                list(result_dynamic['responsibility_ratios'].values())[0]), 2),
        }
        
        # 添加各方详细比例
        for i, (party, ratio) in enumerate(result_fixed['responsibility_ratios'].items()):
            analysis[f'算法1_{party}_比例'] = round(ratio, 2)
            
        for i, (party, ratio) in enumerate(result_dynamic['responsibility_ratios'].items()):
            analysis[f'算法2_{party}_比例'] = round(ratio, 2)
        
        results.append(analysis)
    
    return results


def export_to_excel(results, filename='accident_responsibility_analysis.xlsx'):
    """
    将结果导出到Excel文件
    """
    try:
        import pandas as pd
        
        # 创建DataFrame
        df = pd.DataFrame(results)
        
        # 创建Excel写入器
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # 写入主要分析结果
            df.to_excel(writer, sheet_name='算法对比分析', index=False)
            
            # 创建汇总统计
            summary_data = []
            
            # 按测试类型分组统计
            for test_type in ['正常情况', '极端情况']:
                type_data = df[df['测试类型'] == test_type]
                
                summary_data.append({
                    '测试类型': test_type,
                    '测试案例数': len(type_data),
                    '平均总影响时长差异': round(type_data['总影响时长差异'].mean(), 2),
                    '最大总影响时长差异': round(type_data['总影响时长差异'].max(), 2),
                    '平均起因方比例差异': round(type_data['起因方比例差异'].mean(), 2),
                    '最大起因方比例差异': round(type_data['起因方比例差异'].max(), 2),
                    '算法1平均起因方比例': round(type_data['算法1_起因方比例'].mean(), 2),
                    '算法2平均起因方比例': round(type_data['算法2_起因方比例'].mean(), 2),
                })
            
            # 总体统计
            summary_data.append({
                '测试类型': '总体',
                '测试案例数': len(df),
                '平均总影响时长差异': round(df['总影响时长差异'].mean(), 2),
                '最大总影响时长差异': round(df['总影响时长差异'].max(), 2),
                '平均起因方比例差异': round(df['起因方比例差异'].mean(), 2),
                '最大起因方比例差异': round(df['起因方比例差异'].max(), 2),
                '算法1平均起因方比例': round(df['算法1_起因方比例'].mean(), 2),
                '算法2平均起因方比例': round(df['算法2_起因方比例'].mean(), 2),
            })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='汇总统计', index=False)
            
            # 按参与方数量分组统计
            party_count_stats = []
            for count in sorted(df['参与方数量'].unique()):
                count_data = df[df['参与方数量'] == count]
                party_count_stats.append({
                    '参与方数量': count,
                    '测试案例数': len(count_data),
                    '平均总影响时长差异': round(count_data['总影响时长差异'].mean(), 2),
                    '平均起因方比例差异': round(count_data['起因方比例差异'].mean(), 2),
                    '算法1平均起因方比例': round(count_data['算法1_起因方比例'].mean(), 2),
                    '算法2平均起因方比例': round(count_data['算法2_起因方比例'].mean(), 2),
                })
            
            party_df = pd.DataFrame(party_count_stats)
            party_df.to_excel(writer, sheet_name='按参与方数量统计', index=False)
        
        print(f"结果已导出到 {filename}")
        return True
        
    except ImportError:
        print("需要安装pandas和openpyxl库: pip install pandas openpyxl")
        return False
    except Exception as e:
        print(f"导出Excel时出错: {e}")
        return False


def print_summary_analysis(results):
    """
    打印汇总分析结果
    """
    print("\n" + "="*60)
    print("算法性能汇总分析")
    print("="*60)
    
    # 按测试类型分析
    normal_cases = [r for r in results if r['测试类型'] == '正常情况']
    extreme_cases = [r for r in results if r['测试类型'] == '极端情况']
    
    print(f"\n正常情况测试 ({len(normal_cases)}个案例):")
    if normal_cases:
        avg_diff = sum(r['总影响时长差异'] for r in normal_cases) / len(normal_cases)
        avg_ratio_diff = sum(r['起因方比例差异'] for r in normal_cases) / len(normal_cases)
        print(f"  平均总影响时长差异: {avg_diff:.2f} 分钟")
        print(f"  平均起因方比例差异: {avg_ratio_diff:.2f}%")
    
    print(f"\n极端情况测试 ({len(extreme_cases)}个案例):")
    if extreme_cases:
        avg_diff = sum(r['总影响时长差异'] for r in extreme_cases) / len(extreme_cases)
        avg_ratio_diff = sum(r['起因方比例差异'] for r in extreme_cases) / len(extreme_cases)
        print(f"  平均总影响时长差异: {avg_diff:.2f} 分钟")
        print(f"  平均起因方比例差异: {avg_ratio_diff:.2f}%")
    
    # 找出差异最大的案例
    max_diff_case = max(results, key=lambda x: x['总影响时长差异'])
    print(f"\n总影响时长差异最大的案例:")
    print(f"  测试类型: {max_diff_case['测试类型']}")
    print(f"  原始时长: {max_diff_case['原始时长']}")
    print(f"  差异: {max_diff_case['总影响时长差异']:.2f} 分钟")
    
    max_ratio_case = max(results, key=lambda x: x['起因方比例差异'])
    print(f"\n起因方比例差异最大的案例:")
    print(f"  测试类型: {max_ratio_case['测试类型']}")
    print(f"  原始时长: {max_ratio_case['原始时长']}")
    print(f"  差异: {max_ratio_case['起因方比例差异']:.2f}%")


# 主测试函数
if __name__ == "__main__":
    print("事故定责算法全面测试分析")
    print("固定时长: 30分钟")
    print("="*60)
    
    # 生成测试案例
    test_cases = generate_test_cases()
    print(f"生成了 {len(test_cases)} 个测试案例")
    
    # 分析算法性能
    print("正在分析算法性能...")
    results = analyze_algorithm_performance(test_cases, fixed_duration=30)
    
    # 打印汇总分析
    print_summary_analysis(results)
    
    # 导出到Excel
    print("\n正在导出结果到Excel...")
    export_success = export_to_excel(results, 'test/accident_responsibility_analysis.xlsx')
    
    if export_success:
        print("\n分析完成！请查看Excel文件获取详细对比数据。")
        print("\n建议:")
        
        # 简单的建议逻辑
        all_total_diff = [r['总影响时长差异'] for r in results]
        all_ratio_diff = [r['起因方比例差异'] for r in results]
        
        avg_total_diff = sum(all_total_diff) / len(all_total_diff)
        avg_ratio_diff = sum(all_ratio_diff) / len(all_ratio_diff)
        
        print(f"- 平均总影响时长差异: {avg_total_diff:.2f} 分钟")
        print(f"- 平均起因方比例差异: {avg_ratio_diff:.2f}%")
        
        if avg_total_diff < 10 and avg_ratio_diff < 5:
            print("- 两种算法差异较小，可根据具体业务需求选择")
        elif avg_ratio_diff < 3:
            print("- 建议使用固定算法，计算简单且结果稳定")
        else:
            print("- 建议根据参与方数量选择：参与方少用固定算法，参与方多用非固定算法")
    else:
        print("\nExcel导出失败，但分析已完成。请安装pandas和openpyxl库以导出Excel文件。")