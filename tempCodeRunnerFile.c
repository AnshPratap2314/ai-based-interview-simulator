#include<stdio.h>
#define SIZE 10
int i,n;
int arr[SIZE]={1,2,3,4,5,6};
int sum1=0;
int main(){
    
    for(i=1;i<=n;i++){
        sum1=sum1+arr[i];
        printf("The sum of the array is %d",sum1);
    }

 return 0;
}