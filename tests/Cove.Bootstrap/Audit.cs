using System;using System.Collections.Generic;using System.Linq;using System.Reflection;using System.Text;using System.Threading.Tasks;
internal static class NeutralWindow {internal static int RunDisplay(string[] args)=>throw new Exception("UI must not run in PC audit");}
internal static class BootstrapAudit {
 static int Main(){int n=0;void Yes(bool value){if(!value)throw new Exception("audit_"+n);n++;}
  string label="User::Pkg::com.samsung.tv.bixby-promotion";string[] zero=Enumerable.Repeat("0000000000000000",4).ToArray();
  Yes(Bootstrap.FallbackEligible(5001,5001,label,zero));Yes(!Bootstrap.FallbackEligible(0,0,label,zero));Yes(!Bootstrap.FallbackEligible(5001,0,label,zero));Yes(!Bootstrap.FallbackEligible(5001,5001,"User",zero));
  for(int i=0;i<4;i++){var caps=(string[])zero.Clone();caps[i]="0000000000000001";Yes(!Bootstrap.FallbackEligible(5001,5001,label,caps));}
  Yes(!Bootstrap.FallbackEligible(5001,5001,label,Array.Empty<string>()));
  for(int i=0;i<200;i++)Bootstrap.Emit(new{index=i});
  var events=(Queue<string>)typeof(Bootstrap).GetField("MemoryEvents",BindingFlags.Static|BindingFlags.NonPublic)!.GetValue(null)!;
  Yes(events.Count==64);Yes(events.First().Contains("136"));Yes(events.Last().Contains("199"));Bootstrap.Emit(new{text=new string('x',5000)});Yes(events.Count==64&&events.Last().Contains("199"));
  Parallel.For(0,1000,i=>Bootstrap.Emit(new{parallel=i}));Yes(events.Count==64);Yes(events.All(e=>Encoding.UTF8.GetByteCount(e)<=4096));
  Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new{checks=n,passed=true,native_executed=false,tv_contacted=false}));return 0;
 }
}
