using System;using System.IO;using System.Linq;using System.Reflection.Metadata;using System.Reflection.PortableExecutable;using System.Security.Cryptography;using System.Collections.Generic;using System.Text.Json;
class Audit {
 static object Read(string path){using var f=File.OpenRead(path);using var pe=new PEReader(f);var md=pe.GetMetadataReader();var a=md.GetAssemblyDefinition();var methods=new SortedDictionary<string,string>();int bodies=0,failed=0;
 foreach(var h in md.MethodDefinitions){var m=md.GetMethodDefinition(h);string k=MetadataTokens(h)+":"+md.GetString(m.Name)+":"+Convert.ToHexString(md.GetBlobBytes(m.Signature));string v="none";if(m.RelativeVirtualAddress!=0){try{var b=pe.GetMethodBody(m.RelativeVirtualAddress);v=Convert.ToHexString(SHA256.HashData(b.GetILBytes()));bodies++;}catch(BadImageFormatException){v="non-il";failed++;}}methods[k]=v;}
 return new{path,assembly=md.GetString(a.Name),version=a.Version.ToString(),mvid=md.GetGuid(md.GetModuleDefinition().Mvid).ToString(),machine=pe.PEHeaders.CoffHeader.Machine.ToString(),native_header_size=pe.PEHeaders.CorHeader.ManagedNativeHeaderDirectory.Size,bodies,failed,methods};}
 static int MetadataTokens(MethodDefinitionHandle h)=>System.Reflection.Metadata.Ecma335.MetadataTokens.GetToken(h);
 static int Main(string[] args){var all=args.Select(Read).ToArray();Console.WriteLine(JsonSerializer.Serialize(all));return 0;}
}
