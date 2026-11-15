using System;

internal static class BackChecks {
 internal static void Run(Action<bool> check){
  var gesture=new BackGesture();
  check(!gesture.Up(1));check(gesture.Take(1)==BackDestination.None);
  gesture.Down(BackDestination.Viewer,1);
  check(gesture.Busy);check(gesture.Take(1)==BackDestination.None);
  for(int i=0;i<8;i++)gesture.Down(BackDestination.Viewer,1);
  check(gesture.Up(1));check(!gesture.Up(1));
  gesture.Down(BackDestination.Viewer,1); // Repeat cannot queue a second return.
  check(gesture.Take(1)==BackDestination.Viewer);check(!gesture.Busy);
  check(gesture.Take(1)==BackDestination.None);check(!gesture.Up(1));
  gesture.Down(BackDestination.BrightnessPanel,2);
  gesture.Down(BackDestination.Viewer,2); // Same held press cannot dismiss both.
  check(gesture.Up(2));check(gesture.Take(2)==BackDestination.BrightnessPanel);
  gesture.Down(BackDestination.Viewer,2);gesture.Down(BackDestination.Exit,2);
  check(gesture.Up(2));check(gesture.Take(2)==BackDestination.Exit);
  gesture.Down(BackDestination.Viewer,3);gesture.Cancel();
  check(!gesture.Up(3));check(!gesture.Busy);
  gesture.Down(BackDestination.Viewer,3);check(gesture.Up(3));gesture.Cancel();
  check(gesture.Take(3)==BackDestination.None);
  gesture.Down(BackDestination.Viewer,4);check(!gesture.Up(5));
  check(gesture.Take(5)==BackDestination.None);check(!gesture.Busy);
  gesture.Down(BackDestination.Viewer,5);check(gesture.Up(5));
  check(gesture.Take(6)==BackDestination.None);check(!gesture.Busy);
  gesture.Down(BackDestination.Viewer,6);gesture.Down(BackDestination.BrightnessPanel,7);
  check(gesture.Up(7));check(gesture.Take(7)==BackDestination.BrightnessPanel);
  // A fresh physical press after the preceding release is independent.
  gesture.Down(BackDestination.Viewer,7);check(gesture.Up(7));
  check(gesture.Take(7)==BackDestination.Viewer);check(!gesture.Busy);
 }
}
